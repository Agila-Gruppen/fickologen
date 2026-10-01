from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from schemas.user import UserCreate

from config.database import get_db
from models.user import User
from utils.password import hash_password

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

@router.post("/")
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

