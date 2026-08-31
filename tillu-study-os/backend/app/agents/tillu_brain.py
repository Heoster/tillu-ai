"""Tillu Brain — AI routing layer.

Routes requests: Groq (primary, 15s timeout) → Cerebras (fallback, 15s timeout)
→ rule-based priority sort (final fallback when both AI providers fail).

The Tillu system prompt is defined here and injected into every AI call.
"""
import asyncio
import logging

from app.config import settings
from app.providers.groq_provider import call_groq
from app.providers.cerebras_provider import call_cerebras

logger = logging.getLogger(__name__)

TILLU_SYSTEM_PROMPT = """You are Tillu, a strict but friendly AI study coach for a Class 12 PCM + English + Computer Science board student.
Mission: Help complete syllabus by 30 November and score 90%+.
Always plan using available time, weak chapters, deadline, test scores, and sleep.
Protect sleep schedule. Never suggest distracting activities.
Output must be practical, time-blocked, and specific."""


async def ask_tillu(user_message: str, context: dict) -> str:
    """Send a message to Tillu and get a response.

    Tries Groq first (15s timeout), falls back to Cerebras (15s timeout),
    then falls back to rule-based plan if both fail.

    When RAG is enabled, semantically similar document chunks are retrieved
    and injected into the context before calling the AI providers.

    Args:
        user_message: The user's request/question
        context: Dict with keys like 'tasks', 'weak_chapters', 'test_summary', etc.

    Returns:
        Tillu's response as a string
    """
    # Phase 6: inject RAG document context when enabled
    rag_context: list[dict] = []
    if settings.rag_enabled:
        try:
            from app.agents.search_agent import search_documents
            rag_context = await search_documents(user_message)
        except Exception as e:
            logger.warning("RAG search failed: %s", e)

    messages = [
        {"role": "system", "content": TILLU_SYSTEM_PROMPT},
        {"role": "user", "content": _build_context_message(context, user_message, rag_context)},
    ]

    # Primary: Groq with 15-second timeout
    try:
        return await asyncio.wait_for(call_groq(messages), timeout=15.0)
    except Exception as groq_err:
        logger.warning("Groq failed: %s — falling back to Cerebras", groq_err)

    # Fallback 1: Cerebras with 15-second timeout
    try:
        return await asyncio.wait_for(call_cerebras(messages), timeout=15.0)
    except Exception as cerebras_err:
        logger.warning("Cerebras failed: %s — using rule-based fallback", cerebras_err)

    # Fallback 2: Rule-based — sort tasks by priority_score
    logger.warning("Both AI providers failed. Using rule-based fallback.")
    return _rule_based_plan(context)


def _build_context_message(
    context: dict,
    user_message: str,
    rag_context: list[dict] | None = None,
) -> str:
    """Build a context-enriched user message for the AI.

    When ``rag_context`` contains document chunks (from Phase 6 RAG search),
    they are prepended to the context block so the AI can ground its response
    in the student's own notes and textbooks.
    """
    import json
    parts: list[str] = []

    if rag_context:
        chunk_lines = "\n".join(
            f"[{i+1}] ({c.get('filename', 'doc')}) {c.get('chunk_text', '')}"
            for i, c in enumerate(rag_context)
        )
        parts.append(f"Relevant document excerpts:\n{chunk_lines}")

    context_str = json.dumps(context, default=str, indent=2)
    parts.append(f"Context:\n{context_str}")
    parts.append(f"Request: {user_message}")

    return "\n\n".join(parts)


def _rule_based_plan(context: dict) -> str:
    """Generate a rule-based plan by sorting tasks by priority_score.

    Returns a non-empty string even when context has no tasks.
    """
    tasks = context.get("tasks", [])
    if not tasks:
        return "No tasks available. Please add study tasks first."

    sorted_tasks = sorted(tasks, key=lambda t: t.get("priority_score", 0), reverse=True)
    lines = [
        f"{i+1}. {t.get('chapter_name', t.get('title', 'Unknown'))} "
        f"({t.get('subject_name', t.get('subject', 'Unknown'))}) "
        f"— {t.get('estimated_duration_min', 60)} min"
        for i, t in enumerate(sorted_tasks)
    ]
    return "Rule-based plan (AI unavailable):\n" + "\n".join(lines)
