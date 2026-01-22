from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Union
from uuid import UUID

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: Union[int, str]  # Accept both int and UUID (converted to string)
    email: str
    full_name: Optional[str] = None
    is_email_verified: Optional[bool] = False

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
