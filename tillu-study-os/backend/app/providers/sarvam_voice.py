"""Sarvam AI voice provider — STT and TTS.

Uses httpx.AsyncClient to call the Sarvam API.
Timeout and retry policy are handled by the CALLER (routes/voice.py).
This module surfaces exceptions to the caller.

API reference: https://docs.sarvam.ai/api-reference/text-to-speech/convert
  - STT: POST /speech-to-text  (multipart/form-data)
  - TTS: POST /text-to-speech  (JSON body)
      Request:  {"text": str, "language_code": str, "speaker": str, "model": str}
      Response: {"request_id": str, "audios": ["<base64-wav>", ...]}
"""

import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SARVAM_BASE_URL = "https://api.sarvam.ai"

# bulbul:v2 — stable legacy model with anushka as default female voice.
# bulbul:v1 is no longer listed in the API docs.
SARVAM_TTS_MODEL = "bulbul:v2"
# Valid bulbul:v2 female speakers: anushka, manisha, vidya, arya
# Valid bulbul:v2 male speakers:   abhilash, karun, hitesh
SARVAM_TTS_SPEAKER = "anushka"


async def transcribe_audio(audio_bytes: bytes, language: str = "en-IN") -> str:
    """Transcribe audio bytes to text using the Sarvam STT API.

    Args:
        audio_bytes: Raw audio content (WAV, MP3, etc.).
        language: BCP-47 language code, default ``en-IN``.

    Returns:
        The transcribed text string.

    Raises:
        httpx.HTTPStatusError: on non-2xx response from Sarvam.
        httpx.TimeoutException: on timeout (caller handles this).
        KeyError: if the response JSON is missing the transcript field.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SARVAM_BASE_URL}/speech-to-text",
            headers={"api-subscription-key": settings.sarvam_api_key},
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            data={"language_code": language},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        # Sarvam STT returns {"transcript": "...", ...}
        transcript: str = data["transcript"]
        logger.debug("Sarvam STT transcript: %s", transcript[:100])
        return transcript


async def synthesize_speech(text: str, language: str = "en-IN") -> bytes:
    """Convert text to speech audio bytes using the Sarvam TTS API.

    The Sarvam TTS endpoint returns a JSON body with a base64-encoded WAV
    in the ``audios`` list — it does NOT return raw audio bytes.

    Args:
        text: The text to synthesise (max 1500 chars for bulbul:v2).
        language: BCP-47 target language code, default ``en-IN``.

    Returns:
        Raw WAV audio bytes decoded from the base64 response.

    Raises:
        httpx.HTTPStatusError: on non-2xx response from Sarvam.
        httpx.TimeoutException: on timeout (caller handles this).
        ValueError: if the response body is missing the ``audios`` field.
    """
    # Sarvam TTS rejects texts longer than the model limit; truncate safely.
    MAX_CHARS = 1500
    if len(text) > MAX_CHARS:
        logger.warning(
            "TTS input truncated from %d to %d characters.", len(text), MAX_CHARS
        )
        text = text[:MAX_CHARS]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SARVAM_BASE_URL}/text-to-speech",
            headers={
                "api-subscription-key": settings.sarvam_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "language_code": language,
                "speaker": SARVAM_TTS_SPEAKER,
                "model": SARVAM_TTS_MODEL,
            },
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        audios: list = data.get("audios") or []
        if not audios:
            raise ValueError(
                f"Sarvam TTS response missing 'audios' field. Response: {data}"
            )

        # Decode the first (and usually only) base64-encoded WAV string.
        audio_bytes: bytes = base64.b64decode(audios[0])
        logger.debug(
            "Sarvam TTS produced %d bytes of audio for text length %d",
            len(audio_bytes),
            len(text),
        )
        return audio_bytes
