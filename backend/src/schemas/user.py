from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserBase(BaseModel):
    username : str = Field(..., min_length=3, max_length=50, description="User's username")

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
    Requires username and password.
    """
    password: str = Field(..., min_length=6, description="User's password (minimum 6 characters)")

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
    created_at: datetime
    updated_at: datetime
