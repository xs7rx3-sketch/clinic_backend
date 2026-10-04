from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RealtimeSessionPayload(BaseModel):
    voice: Optional[str] = Field(default="alloy", description="Voice output model (alloy, verse, shimmer, etc.)")
    patient_name: Optional[str] = Field(default=None, description="Patient name for personalized greeting")
    is_vip: Optional[bool] = Field(default=False, description="VIP dignitary protocol flag")
    custom_instructions: Optional[str] = Field(default=None, description="Additional custom instructions")


class RealtimeSessionResponse(BaseModel):
    status: str = Field(default="success", description="Response status")
    client_secret: Optional[str] = Field(default=None, description="Ephemeral token for WebRTC connection")
    session: Dict[str, Any] = Field(default_factory=dict, description="Session configuration returned by OpenAI")
    expires_at: Optional[int] = Field(default=None, description="Unix timestamp of token expiration")
