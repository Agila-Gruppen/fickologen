import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from schemas.chat import ChatRequest, ChatResponse, ChatSource
from services.chat import generate_reply


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


@router.post("/", response_model=ChatResponse, dependencies=[Depends(require_chat_password)])
async def chat(chat_request: ChatRequest):
    """
    Generates the assistant's reply to the conversation.

    Args:
        chat_request: ChatRequest with the conversation, ending with a user message

    Returns:
        ChatResponse with the reply and any sources it was grounded in

    Raises:
        HTTPException: 400 if the last message is not from the user
        HTTPException: 401 if the chat password is wrong
        HTTPException: 502 if the language model call fails
    """
    if chat_request.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The last message must be from the user"
        )

    try:
        reply, chunks = await generate_reply(chat_request.messages)
    except Exception as exc:  # missing key, network, quota, ...
        print(f"Chat failed: {exc!r}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model could not be reached"
        )

    return ChatResponse(
        reply=reply,
        sources=[ChatSource(source=chunk.source, text=chunk.text) for chunk in chunks]
    )
