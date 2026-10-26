from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..models.user import User
from ..schemas.user import AdminPasswordUpdate, AdminUserUpdate, UserData
from ..utils.auth import get_current_admin
from ..utils.password import hash_password


router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)


@router.get("/users", response_model=list[UserData])
async def list_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Lists all users. Admin only.
    """
    return db.query(User).order_by(User.id).all()


@router.patch("/users/{user_id}", response_model=UserData)
async def update_user(
    user_id: int,
    update: AdminUserUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Updates a user's role and/or can_chat flag. Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    if update.role is not None:
        user.role = update.role
    if update.can_chat is not None:
        user.can_chat = update.can_chat

    db.commit()
    db.refresh(user)
    print(f"Admin {admin.username} updated user {user.username}: role={user.role}, can_chat={user.can_chat}")
    return user


@router.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def admin_change_password(
    user_id: int,
    update: AdminPasswordUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Sets a new password for a user. Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    user.password = hash_password(update.new_password)
    db.commit()

    print(f"Admin {admin.username} changed password for user {user.username}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)