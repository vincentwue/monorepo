from .repository import EntitlementsRepository
from .plan_config import PLAN_CONFIG
from .models import Entitlement


class EntitlementsService:
    def __init__(self, repo: EntitlementsRepository):
        self.repo = repo

    # ---------------------------------------------------------
    # Ensure entitlement exists
    # ---------------------------------------------------------
    def ensure_profile(self, user_id: str):
        ent = self.repo.get_by_user(user_id)
        if ent:
            return ent

        new = self.repo.create(
            model=self.repo.get_by_user(user_id) or Entitlement(
                user_id=user_id,
                active_plans={},
            )
        )
        return new

    # ---------------------------------------------------------
    # Check permission for an action
    # ---------------------------------------------------------
    def check_limit(self, user_id: str, product: str, field: str, usage: int):
        ent = self.repo.get_by_user(user_id)
        if not ent:
            raise PermissionError("Entitlements missing for user")

        plan = ent.active_plans.get(product, "free")
        plan_limits = PLAN_CONFIG[product][plan]

        limit = plan_limits.get(field)
        if limit is None:
            return True  # unlimited

        if usage >= limit:
            raise PermissionError(f"Limit exceeded: {usage}/{limit}")

        return True

    # ---------------------------------------------------------
    # Get current plan config for a user and product
    # ---------------------------------------------------------
    def get_plan_info(self, user_id: str, product: str):
        ent = self.repo.get_by_user(user_id)
        if not ent:
            return None

        plan = ent.active_plans.get(product, "free")
        return PLAN_CONFIG[product][plan]
