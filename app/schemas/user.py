from datetime import datetime

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
