import logging
import os
from typing import Optional
import aiohttp
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from src.api.config import LLM_API_KEY

log = logging.getLogger("api.routers.voice")

router = APIRouter(prefix="/api/realtime", tags=["Voice Realtime"])

from src.ai.prompts.voice_prompts import BASE_VOICE_INSTRUCTIONS
from src.api.schemas.voice import RealtimeSessionPayload


@router.api_route("/session", methods=["GET", "POST"])
async def create_realtime_session(request: Request):
    """Generates an ephemeral client secret token from OpenAI for Realtime WebRTC / Voice Agents SDK
    with intelligent interruption handling, silence check-ins, and realistic bilingual hospital persona.
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
    vip_flag = (
        body_data.get("is_vip")
        if body_data.get("is_vip") is not None
        else (query_params.get("is_vip", "").lower() in ("true", "1", "yes"))
    )
    name_str = body_data.get("patient_name") or query_params.get("patient_name") or ""
    extra_instructions = body_data.get("custom_instructions") or query_params.get("custom_instructions") or ""

    # Assemble contextual instructions
    instructions = BASE_VOICE_INSTRUCTIONS.strip()
    if vip_flag:
        instructions += (
            "\n\n### VIP DIGNITARY PROTOCOL:\n"
            "The caller is a Very High-Profile VIP / Dignitary. Address them with supreme deference "
            "('His Highness' / 'صاحب السمو' / 'معاليكم'). Prioritize all their requests with utmost urgency and discretion."
        )
    if name_str:
        instructions += f"\n\n### CALLER IDENTITY:\nThe caller's name is '{name_str}'. Greet them warmly by name."
    if extra_instructions:
        instructions += f"\n\n### ADDITIONAL INSTRUCTIONS:\n{extra_instructions}"

    url = "https://api.openai.com/v1/realtime/client_secrets"
    payload = {
        "session": {
            "type": "realtime",
            "model": "gpt-realtime-2.1",
            "instructions": instructions,
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
                }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Realtime session generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
