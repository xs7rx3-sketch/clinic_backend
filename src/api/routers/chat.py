import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from langchain_core.messages import AIMessage, HumanMessage

from src.api.dependencies import get_ai_graph
from src.api.schemas.chat import ChatRequest, ChatResponse, SaveChatMessageRequest
from src.database.chat_store import clear_chat_history, get_chat_history, save_chat_message

log = logging.getLogger("api.routers.chat")

router = APIRouter(prefix="/api/chat", tags=["AI Chat & History"])


@router.post("", response_model=ChatResponse)
async def chat_with_ai(
    req: ChatRequest,
    graph: Any = Depends(get_ai_graph),
):
    """Processes medical requests through LangGraph AI and persists conversation history in Neon."""
    message = req.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty",
        )

    # Convert conversation history into LangChain messages
    msg_objs = []
    for h in req.history or []:
        role = str(h.get("role") or h.get("sender") or "").lower()
        content = str(h.get("content") or h.get("text") or "").strip()
        if not content:
            continue
        if role in ("user", "human"):
            msg_objs.append(HumanMessage(content=content))
        elif role in ("assistant", "ai", "bot"):
            msg_objs.append(AIMessage(content=content))

    msg_objs.append(HumanMessage(content=message))

    # Save user query to Neon
    user_data = req.user_data or {}
    pid = user_data.get("patient_id")
    if pid:
        save_chat_message(
            patient_id=pid,
            role="user",
            content=message,
            channel="FLUTTER_MOBILE",
            extra_data={"is_vip": user_data.get("is_vip", False)},
        )

    # Invoke LangGraph AI
    state_in = {
        "query": message,
        "user_data": user_data,
        "messages": msg_objs,
    }

    result = await graph.ainvoke(state_in)
    final_answer = result.get("answer") or ""

    # Save AI response to Neon
    if pid and final_answer:
        save_chat_message(
            patient_id=pid,
            role="assistant",
            content=final_answer,
            channel="FLUTTER_MOBILE",
            extra_data={"is_vip": user_data.get("is_vip", False)},
        )

    return ChatResponse(
        status="success",
        answer=final_answer,
        query=message,
    )


@router.get("/history")
async def get_history(
    patient_id: str = Query(..., description="UUID of the patient"),
    limit: int = Query(100, ge=1, le=500),
):
    """Returns stored persistent chat history for a patient from Neon."""
    history = get_chat_history(patient_id=patient_id, limit=limit)
    return {"status": "success", "history": history}


@router.delete("/history")
async def delete_history(
    patient_id: str = Query(..., description="UUID of the patient"),
):
    """Clears stored persistent chat history for a patient in Neon."""
    cleared_count = clear_chat_history(patient_id=patient_id)
    return {"status": "success", "cleared_count": cleared_count}


@router.post("/history/clear")
async def post_clear_history(body: Dict[str, Any]):
    """Alternative POST endpoint to clear chat history in Neon."""
    patient_id = body.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id is required")
    cleared_count = clear_chat_history(patient_id=patient_id)
    return {"status": "success", "cleared_count": cleared_count}


@router.post("/save")
async def save_message(req: SaveChatMessageRequest):
    """Saves external/voice transcript chat messages directly into Neon chat_messages."""
    msg_id = save_chat_message(
        patient_id=req.patient_id,
        role=req.role,
        content=req.content,
        channel=req.channel,
        extra_data=req.extra_data or {},
    )
    return {"status": "success", "message_id": msg_id}
