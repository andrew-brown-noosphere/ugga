"""
AI Chat API Router.

Provides conversational AI for academic advising using RAG.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from src.api.auth import get_current_user, get_optional_user
from src.services.ai_chat_service import get_chat_service, ChatMessage, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    message: str = Field(..., min_length=1, max_length=2000)
    history: Optional[list[dict]] = Field(default=None, max_length=20)


class ChatSource(BaseModel):
    """A source used in generating the response."""
    type: str
    code: Optional[str] = None
    title: Optional[str] = None
    source_type: Optional[str] = None
    similarity: float


class ChatMessageResponse(BaseModel):
    """Response from the AI chat."""
    answer: str
    sources: list[ChatSource]
    model: str


@router.post("", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    """
    Send a message to the AI assistant.

    The AI uses RAG to search courses, syllabi, and program data
    to provide grounded responses about UGA academics.
    """
    try:
        chat_service = get_chat_service()

        # Convert history dict to ChatMessage objects
        history = None
        if request.history:
            history = [
                ChatMessage(role=msg["role"], content=msg["content"])
                for msg in request.history
                if "role" in msg and "content" in msg
            ]

        # Pass user_id for personalized responses when authenticated
        user_id = user.get("id") if user else None

        response = chat_service.chat(
            message=request.message,
            history=history,
            user_id=user_id,
        )

        return ChatMessageResponse(
            answer=response.answer,
            sources=[
                ChatSource(
                    type=s.get("type", "unknown"),
                    code=s.get("code"),
                    title=s.get("title"),
                    source_type=s.get("source_type"),
                    similarity=s.get("similarity", 0),
                )
                for s in response.sources
            ],
            model=response.model,
        )

    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(
                status_code=503,
                detail="AI chat is temporarily unavailable"
            )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/health")
async def chat_health():
    """Check if chat service is available."""
    try:
        chat_service = get_chat_service()
        return {"status": "available", "model": chat_service.model}
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}
