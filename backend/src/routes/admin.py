from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config.database import get_db
from ..models.user import User
from ..schemas.user import AdminPasswordUpdate, AdminUserUpdate, ReminderRunResult, UserData
from ..services import email
from ..services.reminders import send_weekly_reminders
from ..services.user_data import delete_account
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


@router.post("/reminders/send", response_model=ReminderRunResult)
async def send_reminders_now(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Sends the weekly program reminders right away instead of waiting for
    Sunday. Admin only. Users who already got one today are skipped, so
    running it twice does not send twice.

    Raises:
        HTTPException: 503 if sending email is not set up (no SMTP_HOST)
    """
    if not email.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sending email is not set up"
        )
    result = send_weekly_reminders(db)
    print(f"Admin {admin.username} sent the weekly reminders by hand")
    return ReminderRunResult(sent=result.sent, already_sent=result.already_sent, failed=result.failed)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Deletes a user's account and all data tied to it. Admin only.

    Admins cannot delete themselves here (that is done from their own
    account page) or other admins: admin rights come from ADMIN_USERNAMES,
    so remove the name there first.

    Raises:
        HTTPException: 400 if trying to delete yourself or another admin
        HTTPException: 404 if there is no such user
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins delete their own account from the account page"
        )
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot be deleted here; remove them from ADMIN_USERNAMES first"
        )

    username = user.username
    delete_account(user.id, db)
    db.commit()
    print(f"Admin {admin.username} deleted user {username} (ID {user_id})")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
