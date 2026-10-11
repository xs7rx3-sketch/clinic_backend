import logging
import os
from typing import Any, Dict, List, Optional
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from langchain_core.messages import AIMessage, HumanMessage

from src.ai.prompts.voice_prompts import BASE_VOICE_INSTRUCTIONS
from src.api.config import LLM_API_KEY
from src.api.dependencies import get_ai_graph
from src.api.schemas.voice import (
    ExecuteVoiceToolRequest,
    ExecuteVoiceToolResponse,
    RealtimeSessionPayload,
    RealtimeSessionResponse,
)
from src.database.chat_store import save_chat_message
from src.database.queries import fetch_patient_by_id

log = logging.getLogger("api.routers.voice")

router = APIRouter(prefix="/api/realtime", tags=["Voice Realtime"])

# Tool definition registered with OpenAI Realtime API WebRTC sessions
CLINIC_REALTIME_TOOLS = [
    {
        "type": "function",
        "name": "consult_clinic_system",
        "description": (
            "استشر محرك العيادة الذكي ونظام المستشفى لإجراء أي استعلامات أو عمليات: "
            "البحث عن الأقسام والتخصصات والأطباء المتاحين، فحص توفر المواعيد، حجز موعد جديد لمريض، "
            "تعديل أو إلغاء موعد قائم، أو التحقق من مواعيد المريض المسجلة في قاعدة البيانات. "
            "Consult the hospital clinical AI engine to query doctors, check workload & slot availability, "
            "book, reschedule, or cancel patient appointments in the hospital database."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "نص الطلب أو الإجراء السريري المطلوب تنفيذه بالتفصيل بنفس لغة المتصل. "
                        "The patient's request or clinical action to be processed by the clinic AI engine "
                        "(e.g., 'احجز لي موعد مع دكتور قلب غداً' or 'من هم أطباء العيون المتاحين؟' or 'اعرض مواعيدي')."
                    ),
                },
            },
            "required": ["query"],
        },
    }
]


@router.api_route("/session", methods=["GET", "POST"])
async def create_realtime_session(request: Request):
    """Generates an ephemeral client secret token from OpenAI for Realtime WebRTC / Voice Agents SDK
    with intelligent interruption handling, silence check-ins, realistic bilingual hospital persona,
    and direct access to the hospital clinical engine (react_node & sql_nodes).
    """
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM_API_KEY not configured in environment",
        )

    # Parse optional body if provided via POST
    body_data = {}
    if request.method == "POST":
        try:
            body_data = await request.json()
        except Exception:
            body_data = {}

    query_params = request.query_params
    selected_voice = body_data.get("voice") or query_params.get("voice") or "alloy"
    patient_id = body_data.get("patient_id") or query_params.get("patient_id") or ""
    vip_flag = (
        body_data.get("is_vip")
        if body_data.get("is_vip") is not None
        else (query_params.get("is_vip", "").lower() in ("true", "1", "yes"))
    )
    name_str = body_data.get("patient_name") or query_params.get("patient_name") or ""
    extra_instructions = body_data.get("custom_instructions") or query_params.get("custom_instructions") or ""

    # Fetch patient profile if patient_id is provided
    patient_context_str = ""
    if patient_id:
        try:
            patient_record = fetch_patient_by_id(patient_id)
            if patient_record:
                name_str = name_str or patient_record.get("name_ar") or patient_record.get("name_en") or ""
                vip_flag = vip_flag or bool(patient_record.get("is_vip"))
                patient_context_str = (
                    f"\n\n### AUTHENTICATED CALLER RECORD:\n"
                    f"- Patient ID: {patient_id}\n"
                    f"- Patient Name: {name_str}\n"
                    f"- Dignitary Status: {'VIP Royal/Government Protocol' if vip_flag else 'Standard Patient'}\n"
                    f"- Phone: {patient_record.get('phone', 'N/A')}\n"
                )
            else:
                patient_context_str = f"\n\n### CALLER IDENTIFICATION:\nPatient ID: {patient_id}"
        except Exception as e:
            log.warning("Could not fetch patient record for voice session: %s", e)

    # Assemble contextual instructions
    instructions = BASE_VOICE_INSTRUCTIONS.strip()

    # Explicit database & clinical engine access instructions
    instructions += (
        "\n\n### CLINICAL DATABASE & SCHEDULING ACCESS (الوصول لقاعدة البيانات ونظام العيادة):\n"
        "1. You have FULL, REAL-TIME ACCESS to the hospital database, doctors catalog, and appointment scheduling system via the tool `consult_clinic_system`.\n"
        "2. Whenever the caller asks about doctors, specialties, departments, appointment availability, booking an appointment, checking existing appointments, or modifying/canceling bookings:\n"
        "   - You MUST immediately call the `consult_clinic_system` tool with their specific query.\n"
        "   - NEVER tell the caller that you do not have access to the database or that you cannot check appointments or doctors. You DO have access through `consult_clinic_system`.\n"
        "3. Once you receive the tool output, convey the information back to the caller in your warm, concise, spoken conversational voice (1 to 3 natural sentences)."
    )

    if vip_flag:
        instructions += (
            "\n\n### VIP DIGNITARY PROTOCOL:\n"
            "The caller is a Very High-Profile VIP / Dignitary. Address them with supreme deference "
            "('His Highness' / 'صاحب السمو' / 'معاليكم'). Prioritize all their requests with utmost urgency and discretion."
        )
    if name_str:
        instructions += f"\n\n### CALLER IDENTITY:\nThe caller's name is '{name_str}'. Greet them warmly by name."
    if patient_context_str:
        instructions += patient_context_str
    if extra_instructions:
        instructions += f"\n\n### ADDITIONAL INSTRUCTIONS:\n{extra_instructions}"

    url = "https://api.openai.com/v1/realtime/client_secrets"
    payload = {
        "session": {
            "type": "realtime",
            "model": "gpt-realtime-2.1",
            "instructions": instructions,
            "tools": CLINIC_REALTIME_TOOLS,
            "tool_choice": "auto",
            "audio": {
                "input": {
                    "transcription": {
                        "model": "whisper-1",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 750,
                        "create_response": True,
                        "interrupt_response": True,
                    },
                },
                "output": {
                    "voice": selected_voice,
                },
            },
        }
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    log.error("OpenAI Realtime API error: %s", data)
                    raise HTTPException(status_code=resp.status, detail=data)

                client_secret = data.get("value")
                return {
                    "status": "success",
                    "client_secret": client_secret,
                    "session": data.get("session", {}),
                    "expires_at": data.get("expires_at"),
                    "tools": CLINIC_REALTIME_TOOLS,
                }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Realtime session generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/execute-tool", response_model=ExecuteVoiceToolResponse)
async def execute_voice_tool(
    req: ExecuteVoiceToolRequest,
    graph: Any = Depends(get_ai_graph),
):
    """Executes a voice tool call (consult_clinic_system) via LangGraph React & SQL Nodes
    and persists the voice turn in Neon DB.
    """
    query_text = req.query.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter cannot be empty",
        )

    # Prepare user data
    user_data = dict(req.user_data or {})
    pid = req.patient_id or user_data.get("patient_id")
    if pid and "patient_id" not in user_data:
        user_data["patient_id"] = pid

    if pid and ("is_vip" not in user_data or "name" not in user_data):
        try:
            patient_record = fetch_patient_by_id(pid)
            if patient_record:
                user_data.setdefault("is_vip", patient_record.get("is_vip", False))
                user_data.setdefault("name", patient_record.get("name_ar") or patient_record.get("name_en"))
                user_data.setdefault("patient_type", patient_record.get("patient_type"))
        except Exception as e:
            log.warning("Could not hydrate patient record for tool execution: %s", e)

    # Convert optional conversation history into LangChain messages
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

    msg_objs.append(HumanMessage(content=query_text))

    # Persist caller voice query to Neon DB if patient_id is present
    if pid:
        try:
            save_chat_message(
                patient_id=pid,
                role="user",
                content=query_text,
                channel="VOICE_CALL",
                extra_data={"tool": req.tool_name, "is_vip": user_data.get("is_vip", False)},
            )
        except Exception as e:
            log.warning("Failed to save voice chat query: %s", e)

    # Invoke LangGraph AI (react_node orchestrates sql_nodes and formulates voice-ready response)
    state_in = {
        "query": query_text,
        "user_data": user_data,
        "messages": msg_objs,
    }

    try:
        result = await graph.ainvoke(state_in)
        final_answer = result.get("answer") or ""
    except Exception as e:
        log.exception("Error executing AI Graph in voice tool: %s", e)
        final_answer = "عذراً، حدث خطأ أثناء الاتصال بنظام المستشفى. يرجى إعادة المحاولة."

    # Persist assistant response to Neon DB
    if pid and final_answer:
        try:
            save_chat_message(
                patient_id=pid,
                role="assistant",
                content=final_answer,
                channel="VOICE_CALL",
                extra_data={"tool": req.tool_name, "is_vip": user_data.get("is_vip", False)},
            )
        except Exception as e:
            log.warning("Failed to save voice assistant response: %s", e)

    return ExecuteVoiceToolResponse(
        status="success",
        tool_name=req.tool_name or "consult_clinic_system",
        output=final_answer,
    )

