from datetime import datetime

from pydantic import BaseModel


class UserSettingsUpdate(BaseModel):
    alert_low_balance: bool | None = None
    monthly_reset: bool | None = None
    block_negative_balance: bool | None = None


class UserSettingsResponse(BaseModel):
    id: str
    user_id: str
    alert_low_balance: bool
    monthly_reset: bool
    block_negative_balance: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
