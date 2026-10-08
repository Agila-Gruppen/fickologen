from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="User's username")

    @field_validator('username')
    @classmethod
    def username_must_be_alphanumeric(cls, v: str) -> str:
        """Validates that username contains only letters, numbers, and underscores"""
        if not v.replace('_', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v.strip()


class UserCreate(UserBase):
    """
    Schema for creating a new user.
    Required: username, password, email.
    Optional: first_name, last_name, birth_year, phone, gender, city.
    role and can_chat are NOT accepted here (safe default: user without chat access).
    """
    password: str = Field(..., min_length=6, description="User's password (minimum 6 characters)")
    email: Optional[EmailStr] = Field(None, description="User's email (recommended)")

    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    birth_year: Optional[int] = Field(None, ge=1900, le=2026)
    phone: Optional[str] = Field(None, max_length=32)
    gender: Optional[str] = Field(None, max_length=32)
    city: Optional[str] = Field(None, max_length=100)

    @field_validator('password')
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        """Simple validation that the password has at least 6 characters"""
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class UserData(BaseModel):
    """
    Schema for the data stored about a user.
    Lets users see what is saved about them. The password is stored
    only as a hash and is never returned.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[EmailStr] = None
    role: str
    can_chat: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_year: Optional[int] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    city: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    """
    Schema for admin updates to a user. Only role and can_chat can be changed here.
    """
    role: Optional[Literal["user", "admin"]] = None
    can_chat: Optional[bool] = None
