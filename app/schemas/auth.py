from pydantic import BaseModel, EmailStr


class RequestLoginCode(BaseModel):
    email: EmailStr


class VerifyLoginCode(BaseModel):
    email: EmailStr
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None

    model_config = {"from_attributes": True}
