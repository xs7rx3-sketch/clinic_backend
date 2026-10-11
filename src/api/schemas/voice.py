from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RealtimeSessionPayload(BaseModel):
    voice: Optional[str] = Field(default="alloy", description="Voice output model (alloy, verse, shimmer, etc.)")
    patient_id: Optional[str] = Field(default=None, description="UUID of the patient")
    patient_name: Optional[str] = Field(default=None, description="Patient name for personalized greeting")
    is_vip: Optional[bool] = Field(default=False, description="VIP dignitary protocol flag")
    custom_instructions: Optional[str] = Field(default=None, description="Additional custom instructions")


class RealtimeSessionResponse(BaseModel):
    status: str = Field(default="success", description="Response status")
    client_secret: Optional[str] = Field(default=None, description="Ephemeral token for WebRTC connection")
    session: Dict[str, Any] = Field(default_factory=dict, description="Session configuration returned by OpenAI")
    expires_at: Optional[int] = Field(default=None, description="Unix timestamp of token expiration")
    tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="Registered tools available in session")


class ExecuteVoiceToolRequest(BaseModel):
    tool_name: Optional[str] = Field(default="consult_clinic_system", description="Name of the tool requested by OpenAI")
    query: str = Field(..., description="Query or statement to process through the AI graph")
    patient_id: Optional[str] = Field(default=None, description="UUID of the patient if known")
    user_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient context and metadata")
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Recent conversation turns if available")


class ExecuteVoiceToolResponse(BaseModel):
    status: str = Field(default="success", description="Execution status")
    tool_name: str = Field(..., description="Tool that was executed")
    output: str = Field(..., description="Structured clinical response from LangGraph/React nodes")

