import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.schemas import ChatRequest, ChatResponse
from app.services.ai_agent import chat as agent_chat
from app.config import settings

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server; the AI assistant is disabled.",
        )
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    try:
        reply = await agent_chat(current_user["_id"], payload.message)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Assistant error: {e}")
    return ChatResponse(reply=reply, conversation_id=conversation_id)
