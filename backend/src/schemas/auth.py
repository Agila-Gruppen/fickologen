from pydantic import BaseModel, Field, field_validator

from .user import MIN_PASSWORD_LENGTH, check_password

class LoginRequest(BaseModel):
    """
    Schema for login request.
    User provides username and password.
    """
    username: str
    password: str


class TokenResponse(BaseModel):
    """
    Schema for token response.
    Returns message about token being set in cookie.
    """
    message: str
    user_id: int
    username: str


class CurrentUser(BaseModel):
    """
    Schema for current authenticated user info.
    """
    user_id: int
    username: str


class PasswordReset(BaseModel):
    """
    Schema for resetting a forgotten password with the recovery code.
    """
    username: str
    recovery_code: str
    new_password: str = Field(..., min_length=MIN_PASSWORD_LENGTH)

    @field_validator('new_password')
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        return check_password(v)


class PasswordResetResponse(BaseModel):
    """
    Schema returned after a reset. The used recovery code is replaced by
    recovery_code, which is shown only this once.
    """
    message: str
    recovery_code: str
