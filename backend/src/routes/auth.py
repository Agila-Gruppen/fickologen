from fastapi import APIRouter, HTTPException, status, Depends, Cookie, Response
from sqlalchemy.orm import Session
from ..schemas.auth import LoginRequest, TokenResponse, CurrentUser, PasswordReset, PasswordResetResponse

from ..models.user import User
from ..config.database import get_db
from ..utils.password import generate_recovery_code, hash_password, normalize_recovery_code, verify_password
from ..utils.auth import create_access_token, decode_access_token, get_current_user


# Create a router for auth endpoints
router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Login endpoint that authenticates a user and returns a JWT token as HTTP-only cookie.

    Args:
        login_data: LoginRequest with email (username) and password
        response: FastAPI Response to set cookie
        db: Database session (injected by FastAPI)

    Returns:
        TokenResponse with success message and user info

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Find user by username
    user = db.query(User).filter(User.username == login_data.username).first()
    print(user)
    if not user:
        print(f"Login failed: User with username {login_data.username} not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Verify password
    if not verify_password(login_data.password, user.password):
        print(f"Login failed: Invalid password for {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Create JWT token
    token_data = {
        "user_id": user.id,
        "username": user.username
    }
    access_token = create_access_token(data=token_data)

    # Set HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access
        max_age=1800,   # 30 minutes
        samesite="lax"  # CSRF protection
    )

    print(f"User {user.username} logged in successfully")

    return TokenResponse(
        message="Login successful! Token set as HTTP-only cookie",
        user_id=user.id,
        username=user.username
    )

    
@router.get("/secret")
async def get_secret(current_user: CurrentUser = Depends(get_current_user)):
    """
    Protected endpoint that requires authentication.
    Returns a secret message only for authenticated users.

    Args:
        current_user: Current authenticated user (injected by dependency)

    Returns:
        Secret message with user info
    """
    print(f"User {current_user.username} accessed the secret endpoint")

    return {
        "message": "This is a secret message!",
        "secret": "The answer to life, the universe, and everything is 42",
        "user": {
            "user_id": current_user.user_id,
            "username": current_user.username
        },
        "note": "You can only see this because you are authenticated!"
    }

@router.post("/logout")
async def logout(response: Response):
    """
    Logout endpoint that clears the JWT cookie.

    Args:
        response: FastAPI Response to clear cookie

    Returns:
        Success message
    """
    response.delete_cookie(key="access_token")
    print("User logged out successfully")
    return {"message": "Logged out successfully"}


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(reset: PasswordReset, db: Session = Depends(get_db)):
    """
    Sets a new password for a user who forgot theirs, using the recovery
    code they got when the account was created. The code can be used only
    once: it is replaced by a new one, returned in the response.

    Args:
        reset: PasswordReset with username, recovery code and new password
        db: Database session (injected by FastAPI)

    Returns:
        PasswordResetResponse with the new recovery code

    Raises:
        HTTPException: 400 if the username or recovery code is wrong
    """
    user = db.query(User).filter(User.username == reset.username.strip()).first()
    code = normalize_recovery_code(reset.recovery_code)
    # Same answer for an unknown user, a user without a code and a wrong
    # code, so the endpoint does not reveal which usernames exist.
    if not user or not user.recovery_code or not verify_password(code, user.recovery_code):
        print(f"Password reset failed for {reset.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or recovery code"
        )

    new_code = generate_recovery_code()
    user.password = hash_password(reset.new_password)
    user.recovery_code = hash_password(new_code)
    db.commit()

    print(f"User {user.username} reset their password")
    return PasswordResetResponse(
        message="Password reset. Log in with the new password.",
        recovery_code=new_code
    )
