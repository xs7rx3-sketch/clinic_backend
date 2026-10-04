import logging
import os
import aiohttp
from fastapi import APIRouter, HTTPException, status

from src.api.config import LLM_API_KEY

log = logging.getLogger("api.routers.voice")

router = APIRouter(prefix="/api/realtime", tags=["Voice Realtime"])


@router.api_route("/session", methods=["GET", "POST"])
async def create_realtime_session():
    """Generates an ephemeral client secret token from OpenAI for Realtime WebRTC / Voice Agents SDK."""
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM_API_KEY not configured in environment",
        )

    url = "https://api.openai.com/v1/realtime/client_secrets"
    payload = {
        "session": {
            "type": "realtime",
            "model": "gpt-realtime-2.1",
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
