from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ..config.database import get_db
from ..models.conversation import Conversation
from ..models.message import Message
from ..models.user import User
from ..schemas.chat import ChatRequest, ChatResponse, ChatSource
from ..services.chat import generate_reply
from ..utils.auth import decode_access_token


router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)

def allow_chat(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Allows the chat for logged-in users with chat access.

    A user has chat access when their role is 'admin' or can_chat is True.

    Raises:
        HTTPException: 401 if not logged in or the session is invalid.
        HTTPException: 403 if logged in but not allowed to chat.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not logged in"
        )

    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session payload"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists"
        )

    if user.role != "admin" and not user.can_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat access not granted for this account"
        )

    return user

def _resolve_conversation(
    user: User,
    db: Session,
    *,
    conversation_id: Optional[int] = None,
    first_message: Optional[str] = None,
) -> Conversation:
    """
    Returns the conversation to append messages to.

    If conversation_id is given, it must belong to the user — otherwise 404.
    If omitted, a fresh conversation is created, titled from the first user
    message (whitespace collapsed, trimmed to 60 chars).
    """
    if conversation_id is not None:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
            .first()
        )
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        return conv

    title: Optional[str] = None
    if first_message:
        clean = " ".join(first_message.split())
        if clean:
            title = clean[:60]
    conv = Conversation(user_id=user.id, title=title)
    db.add(conv)
    db.flush()
    return conv


@router.post("/", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest,
    user: Optional[User] = Depends(allow_chat),
    db: Session = Depends(get_db),
):
    """
    Generates the assistant's reply, and persists both messages when the
    caller is identified as a logged-in user. Anonymous CHAT_PASSWORD
    callers get the reply but nothing is saved.

    Raises:
        HTTPException: 400 if the last message is not from the user
        HTTPException: 401 if the caller is not authorized
        HTTPException: 502 if the language model call fails
    """
    if chat_request.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The last message must be from the user"
        )

    try:
        result = await generate_reply(
            chat_request.messages, chat_request.engine, program_week=chat_request.program_week
        )
    except Exception as exc:
        print(f"Chat failed: {exc!r}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model could not be reached"
        )

    saved_conversation_id: int | None = None
    if user is not None:
        try:
            conv = _resolve_conversation(
                user,
                db,
                conversation_id=chat_request.conversation_id,
                first_message=chat_request.messages[-1].content,
            )
            db.add(Message(
                conversation_id=conv.id,
                role="user",
                content=chat_request.messages[-1].content,
            ))
            db.add(Message(
                conversation_id=conv.id,
                role="assistant",
                content=result.reply,
                category=result.category,
                via=result.via,
                llm_used=result.llm_used,
            ))
            # Bump updated_at so the conversation moves to the top of the saved list.
            conv.updated_at = func.now()
            db.commit()
            saved_conversation_id = conv.id
        except HTTPException:
            raise
        except Exception as exc:
            print(f"Failed to persist chat for user {user.id}: {exc!r}")
            db.rollback()

    return ChatResponse(
        reply=result.reply,
        sources=[ChatSource(source=chunk.source, text=chunk.text) for chunk in result.chunks],
        engine=chat_request.engine,
        category=result.category,
        via=result.via,
        llm_used=result.llm_used,
        conversation_id=saved_conversation_id,
    )