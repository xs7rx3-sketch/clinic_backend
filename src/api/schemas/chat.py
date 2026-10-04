from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Medical query or message text")
    user_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contextual user details like patient_id, is_vip")
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Prior conversation messages")


class ChatResponse(BaseModel):
    status: str = "success"
    answer: str
    query: str


class SaveChatMessageRequest(BaseModel):
    patient_id: str
    role: str = "user"
    content: str
    channel: str = "FLUTTER_MOBILE"
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
