from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..config.database import get_db
from ..models.conversation import Conversation
from ..schemas.auth import CurrentUser
from ..schemas.conversation import ConversationData, ConversationRename, ConversationWithMessages
from ..schemas.user_data import DeletedCount
from ..services.user_data import delete_conversations
from ..utils.auth import get_current_user


router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)


def _get_own_conversation(
    conversation_id: int,
    current_user: CurrentUser,
    db: Session,
) -> Conversation:
    """
    Looks up a conversation and verifies it belongs to the logged-in user.

    Returns 404 (not 403) if the conversation belongs to someone else, to avoid
    leaking which ids exist.
    """
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.user_id,
        )
        .first()
    )
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return conv


@router.get("/", response_model=list[ConversationData])
async def list_my_conversations(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the logged-in user's conversations, most-recently-updated first.
    Uses the composite index on (user_id, updated_at) from PLAN-64.
    """
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.get("/{conversation_id}/messages", response_model=ConversationWithMessages)
async def get_conversation_with_messages(
    conversation_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns a single conversation with all its messages in chronological order.
    The messages relationship on the model already orders by created_at ASC.
    """
    return _get_own_conversation(conversation_id, current_user, db)


@router.patch("/{conversation_id}", response_model=ConversationData)
async def rename_conversation(
    conversation_id: int,
    rename: ConversationRename,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Changes the title of one of the logged-in user's conversations.

    updated_at is left as it was, so renaming does not move the chat to the top of
    the saved list.
    """
    conv = _get_own_conversation(conversation_id, current_user, db)
    conv.title = rename.title
    flag_modified(conv, "updated_at")  # keep the value instead of letting onupdate bump it
    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a conversation. All its messages are removed by the CASCADE
    on messages.conversation_id.
    """
    conv = _get_own_conversation(conversation_id, current_user, db)
    db.delete(conv)
    db.commit()
    print(f"Deleted conversation {conversation_id} for user {current_user.user_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/", response_model=DeletedCount)
async def delete_all_conversations(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes all the logged-in user's conversations and their messages.

    Returns:
        DeletedCount with how many conversations were removed
    """
    deleted = delete_conversations(current_user.user_id, db)
    db.commit()
    print(f"Deleted all {deleted} conversations for user {current_user.user_id}")
    return DeletedCount(deleted=deleted)
