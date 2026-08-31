"""Voice route — Sarvam STT/TTS integration (Phase 4).

Endpoints:
  POST /voice/transcribe  — Upload audio → transcript → Tillu reply → TTS audio
  GET  /voice/status      — Returns whether the voice feature is enabled

Gated by SARVAM_ENABLED=true in .env.  When disabled, all mutating endpoints
return HTTP 503 with a descriptive message.
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from app.agents.tillu_brain import ask_tillu
from app.config import settings
from app.providers.sarvam_voice import synthesize_speech, transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])

_FEATURE_DISABLED_DETAIL = (
    "Voice feature not enabled. Set SARVAM_ENABLED=true to activate."
)

# Timeout forwarded to the Sarvam provider calls (the provider sets a
# separate 30 s httpx timeout; this outer guard catches stalls).
_SARVAM_TIMEOUT = 25.0


@router.post("/transcribe")
async def transcribe_and_respond(audio: UploadFile) -> Response:
    """Accept an audio upload, transcribe it with Sarvam STT, pass the
    transcript to Tillu, convert the response to speech via Sarvam TTS,
    and return the audio bytes.

    The transcript is also included in the ``X-Transcript`` response header
    so the frontend can display it as text.

    Returns HTTP 503 when the voice feature is disabled.
    """
    if not settings.sarvam_enabled:
        raise HTTPException(status_code=503, detail=_FEATURE_DISABLED_DETAIL)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    # 1. Speech → Text
    try:
        transcript = await asyncio.wait_for(
            transcribe_audio(audio_bytes),
            timeout=_SARVAM_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error("Sarvam STT timed out after %.0f s", _SARVAM_TIMEOUT)
        raise HTTPException(
            status_code=504, detail="Speech-to-text request timed out."
        )
    except Exception as exc:
        logger.error("Sarvam STT failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Speech-to-text error: {exc}"
        )

    # 2. Text → Tillu response
    tillu_response = await ask_tillu(transcript, {})

    # 3. Tillu response → Speech
    try:
        response_audio = await asyncio.wait_for(
            synthesize_speech(tillu_response),
            timeout=_SARVAM_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error("Sarvam TTS timed out after %.0f s", _SARVAM_TIMEOUT)
        raise HTTPException(
            status_code=504, detail="Text-to-speech request timed out."
        )
    except Exception as exc:
        logger.error("Sarvam TTS failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Text-to-speech error: {exc}"
        )

    return Response(
        content=response_audio,
        media_type="audio/wav",
        headers={"X-Transcript": transcript},
    )


@router.get("/status")
async def voice_status() -> dict:
    """Return whether the Sarvam voice feature is currently enabled."""
    return {"enabled": settings.sarvam_enabled, "provider": "sarvam"}
