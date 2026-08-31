"""Chat route — Tillu AI chat endpoint."""
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.tillu_brain import ask_tillu

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    context: dict = {}


@router.post("")
async def chat(body: ChatRequest):
    """Accept a message, forward it to Tillu, and return the response."""
    response = await ask_tillu(body.message, body.context)
    return {"response": response}
