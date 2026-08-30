"""Chat route — placeholder implementation.

Full Tillu AI chat endpoint will be wired in task 11.9.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    context: dict = {}


@router.post("")
async def chat(body: ChatRequest):
    """Accept a message, forward it to Tillu, and return the response."""
    # TODO: implement in task 11.9
    return {"response": "Tillu is not yet wired up. Come back soon!"}
