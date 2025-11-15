from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Entitlement(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str                               # Ory identity ID
    lemon_customer_id: Optional[str] = None
    lemon_subscription_id: Optional[str] = None

    # product → plan (e.g. { "ideas": "basic", "music_video": "pro" })
    active_plans: dict[str, str] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }
