from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..schemas.auth import CurrentUser
from ..schemas.user import UserCreate, UserData
from ..config.database import get_db
from ..models.user import User
from ..utils.auth import get_current_user
from ..utils.password import hash_password
from ..utils.admin import is_admin_username

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/", response_model=UserData)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Creates a new user. can_chat always starts false; role gets 'admin'
    automatically if the username is listed in ADMIN_USERNAMES, otherwise 'user'.
    """
    if db.query(User).filter(User.username == user.username).first():
        print(f"Attempted to create user with existing username: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with username '{user.username}' already exists"
        )

    if db.query(User).filter(User.email == user.email).first():
        print(f"Attempted to create user with existing email: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with email '{user.email}' already exists"
        )

    hashed_password = hash_password(user.password)

    role = "admin" if is_admin_username(user.username) else "user"

    new_user = User(
        username=user.username,
        password=hashed_password,
        email=user.email,
        role=role,
        first_name=user.first_name,
        last_name=user.last_name,
        birth_year=user.birth_year,
        phone=user.phone,
        gender=user.gender,
        city=user.city,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    print(f"Created new user: {new_user.username} (ID: {new_user.id}, role: {new_user.role})")
    return new_user


def _get_own_user(current_user: CurrentUser, db: Session) -> User:
    """
    Looks up the logged-in user's row.

    Raises:
        HTTPException: 404 if the account no longer exists
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    return user


@router.get("/me", response_model=UserData)
async def get_my_data(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns everything stored about the logged-in user.
    """
    return _get_own_user(current_user, db)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(response: Response, current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Deletes the logged-in user's account and all data tied to it,
    and clears the login cookie.
    """
    user = _get_own_user(current_user, db)

    # Delete rows from other tables tied to the user here once there are any.
    db.delete(user)
    db.commit()

    response.delete_cookie(key="access_token")
    print(f"Deleted user ID {current_user.user_id}")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response