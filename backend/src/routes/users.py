from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..schemas.auth import CurrentUser
from ..schemas.user import (
    PasswordChange,
    RecoveryCodeRequest,
    RecoveryCodeResponse,
    UserCreate,
    UserCreated,
    UserData,
    UserSelfUpdate,
)
from ..config.database import get_db
from ..models.user import User
from ..utils.auth import get_current_user
from ..utils.password import generate_recovery_code, hash_password, verify_password
from ..utils.admin import is_admin_username
from ..schemas.user_data import DeletedContent
from ..services.user_data import delete_conversations, delete_cbt_progress, delete_diary_entries

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/", response_model=UserCreated)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Creates a new user. can_chat always starts false; role gets 'admin'
    automatically if the username is listed in ADMIN_USERNAMES, otherwise 'user'.
    The response includes a recovery code for resetting a forgotten password;
    it is returned only here and stored only as a hash.
    """
    if db.query(User).filter(User.username == user.username).first():
        print(f"Attempted to create user with existing username: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with username '{user.username}' already exists"
        )

    if user.email and db.query(User).filter(User.email == user.email).first():
        print(f"Attempted to create user with existing email: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with email '{user.email}' already exists"
        )

    hashed_password = hash_password(user.password)
    recovery_code = generate_recovery_code()

    role = "admin" if is_admin_username(user.username) else "user"

    new_user = User(
        username=user.username,
        password=hashed_password,
        recovery_code=hash_password(recovery_code),
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
    return UserCreated(**UserData.model_validate(new_user).model_dump(), recovery_code=recovery_code)


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

    # Conversations, messages, diary entries and CBT progress go with it
    # through ON DELETE CASCADE on their user_id foreign keys.
    db.delete(user)
    db.commit()

    response.delete_cookie(key="access_token")
    print(f"Deleted user ID {current_user.user_id}")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


def _require_current_password(user: User, password: str) -> None:
    """
    Raises:
        HTTPException: 400 if the password is wrong. Not 401, which means
            the login itself has expired.
    """
    if not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    change: PasswordChange,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Changes the logged-in user's password. Requires the current password.

    Raises:
        HTTPException: 400 if the current password is wrong
        HTTPException: 401 if not logged in
        HTTPException: 404 if the account no longer exists
    """
    user = _get_own_user(current_user, db)
    _require_current_password(user, change.current_password)

    user.password = hash_password(change.new_password)
    db.commit()

    print(f"User ID {user.id} changed their password")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/recovery-code", response_model=RecoveryCodeResponse)
async def new_recovery_code(
    request: RecoveryCodeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Issues a new recovery code for the logged-in user, replacing the old one.
    Also how accounts created before recovery codes existed get one.

    Raises:
        HTTPException: 400 if the current password is wrong
        HTTPException: 401 if not logged in
        HTTPException: 404 if the account no longer exists
    """
    user = _get_own_user(current_user, db)
    _require_current_password(user, request.current_password)

    recovery_code = generate_recovery_code()
    user.recovery_code = hash_password(recovery_code)
    db.commit()

    print(f"User ID {user.id} got a new recovery code")
    return RecoveryCodeResponse(recovery_code=recovery_code)


@router.delete("/me/data", response_model=DeletedContent)
async def delete_my_content(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes everything the logged-in user has created – conversations with
    their messages, diary entries and CBT progress – but keeps the account,
    so they can go on using Fickologen with a clean slate.

    Returns:
        DeletedContent with how many conversations and diary entries were removed

    Raises:
        HTTPException: 401 if not logged in
        HTTPException: 404 if the account no longer exists
    """
    user = _get_own_user(current_user, db)
    conversations = delete_conversations(user.id, db)
    diary_entries = delete_diary_entries(user.id, db)
    delete_cbt_progress(user.id, db)
    db.commit()

    print(f"Deleted all content for user ID {user.id}: {conversations} conversations, {diary_entries} diary entries")
    return DeletedContent(conversations=conversations, diary_entries=diary_entries)
