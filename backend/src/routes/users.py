from fastapi import FastAPI, APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from ..schemas.auth import CurrentUser
from ..schemas.user import UserCreate, UserData

from ..config.database import get_db
from ..models.user import User
from ..utils.auth import get_current_user
from ..utils.password import hash_password

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.get("/")
async def get_user():
    return {
        "user" : "Hello",
        "password" : "World!"
    }

@router.post("/", response_model=UserData)
async def create_user(user : UserCreate, db : Session = Depends(get_db)):
    """
    Creates a new user.

    Args:
        user: UserCreate schema with user data
        db: Database session (injected by FastAPI)

    Returns:
        The newly created user (without password)

    Raises:
        HTTPException: 400 if the username already exists
    """

    # Check if the username already exists
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        print(f"Attempted to create user with existing username: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with username '{user.username}' already exists"
        )

    # Hash the password before storing
    hashed_password = hash_password(user.password)

    # Create the new user
    new_user = User(
        username=user.username,
        password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    print(f"Created new user: {new_user.username} (ID: {new_user.id})")
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

    Args:
        current_user: Current authenticated user (injected by dependency)
        db: Database session (injected by FastAPI)

    Returns:
        UserData with the stored fields (the password hash is left out)

    Raises:
        HTTPException: 401 if not logged in
        HTTPException: 404 if the account no longer exists
    """
    return _get_own_user(current_user, db)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(response: Response, current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Deletes the logged-in user's account and all data tied to it,
    and clears the login cookie.

    Args:
        response: FastAPI Response to clear cookie
        current_user: Current authenticated user (injected by dependency)
        db: Database session (injected by FastAPI)

    Returns:
        204 when the account is deleted

    Raises:
        HTTPException: 401 if not logged in
        HTTPException: 404 if the account no longer exists
    """
    user = _get_own_user(current_user, db)

    # Delete rows from other tables tied to the user here once there are any.
    db.delete(user)
    db.commit()

    response.delete_cookie(key="access_token")
    print(f"Deleted user ID {current_user.user_id}")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response

