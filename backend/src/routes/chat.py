import hmac
import os
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
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


def require_chat_password(x_chat_password: Optional[str] = Header(None)) -> None:
    """
    Dependency that guards the chat with the shared prototype password.

    Args:
        x_chat_password: Password from the X-Chat-Password header

    Raises:
        HTTPException: 401 if the password is missing or wrong, or if no
            CHAT_PASSWORD is configured (fail closed)
    """
    expected = os.environ.get("CHAT_PASSWORD", "")
    provided = x_chat_password or ""
    if not expected or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid chat password"
        )
        
def allow_chat(
    x_chat_password: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Allows the chat for either:
      - a logged-in user identified by the access_token cookie (returns User), or
      - anyone who knows the shared CHAT_PASSWORD (returns None).

    Raises:
        HTTPException: 401 if neither path checks out.
    """
    if access_token:
        payload = decode_access_token(access_token)
        if payload:
            user_id = payload.get("user_id")
            if isinstance(user_id, int):
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user

    expected = os.environ.get("CHAT_PASSWORD", "")
    provided = x_chat_password or ""
    if expected and hmac.compare_digest(provided.encode(), expected.encode()):
        return None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authorized to chat"
    )


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


@router.post("/unlock", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_chat_password)])
async def unlock():
    """
    Checks the chat password without sending a message.

    Returns:
        204 if the password is correct

    Raises:
        HTTPException: 401 if the password is wrong
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        result = await generate_reply(chat_request.messages, chat_request.engine)
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