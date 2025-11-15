from typing import Optional
from pymongo import MongoClient
from .models import Entitlement
from datetime import datetime


class EntitlementsRepository:
    def __init__(self, mongo_uri: str, db_name: str = "core"):
        self.client = MongoClient(mongo_uri)
        self.collection = self.client[db_name]["entitlements"]

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------
    def get_by_user(self, user_id: str) -> Optional[Entitlement]:
        raw = self.collection.find_one({"user_id": user_id})
        return Entitlement.model_validate(raw) if raw else None

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    def create(self, model: Entitlement) -> Entitlement:
        data = model.model_dump(by_alias=True)
        res = self.collection.insert_one(data)
        model.id = str(res.inserted_id)
        return model

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------
    def update(self, user_id: str, updates: dict) -> Entitlement:
        updates["updated_at"] = datetime.utcnow()
        raw = self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": updates},
            return_document=True,
        )
        return Entitlement.model_validate(raw)

    # ---------------------------------------------------------
    # UPSERT PLAN
    # ---------------------------------------------------------
    def set_plan(self, user_id: str, product: str, plan: str) -> Entitlement:
        raw = self.collection.find_one_and_update(
            {"user_id": user_id},
            {
                "$set": {f"active_plans.{product}": plan,
                         "updated_at": datetime.utcnow()}
            },
            upsert=True,
            return_document=True,
        )
        return Entitlement.model_validate(raw)
