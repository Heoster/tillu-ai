"""Document management routes — Phase 6 RAG.

Mounted at ``/documents`` in ``main.py``.

All endpoints return HTTP 503 when ``RAG_ENABLED=false``.

Endpoints
---------
POST /documents/upload
    Accepts a multipart form upload (file + subject_id).
    Chunks, embeds, and stores the document via ``search_agent.ingest_document``.
    Returns ``{"chunks_stored": N, "filename": "..."}``.

GET /documents
    Returns unique filenames grouped by ``subject_id``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.agents.search_agent import ingest_document
from app.config import settings
from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

def _require_rag() -> None:
    """Raise HTTP 503 when RAG feature flag is off."""
    if not settings.rag_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG document search is disabled. "
                "Set RAG_ENABLED=true in backend/.env to enable."
            ),
        )


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_document(
    file: UploadFile,
    subject_id: str = Form(...),
):
    """Ingest a document: chunk → embed → store in the ``documents`` table.

    Args:
        file: Uploaded file (.pdf or .txt).
        subject_id: UUID (or slug) of the subject this document belongs to.

    Returns:
        JSON ``{"chunks_stored": N, "filename": "..."}``.

    Raises:
        HTTPException(503): when RAG is disabled.
        HTTPException(400): when the file is empty or produces no text.
        HTTPException(415): when the file type is not supported.
    """
    _require_rag()

    content_type = file.content_type or ""
    filename = file.filename or "unknown"

    if content_type not in ("text/plain", "application/pdf") and not (
        filename.lower().endswith((".txt", ".pdf"))
    ):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. "
                "Please upload a PDF (.pdf) or plain-text (.txt) file."
            ),
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    stored_rows = await ingest_document(
        subject_id=subject_id,
        filename=filename,
        content=content,
        content_type=content_type,
    )

    return {
        "chunks_stored": len(stored_rows),
        "filename": filename,
    }


# ---------------------------------------------------------------------------
# List documents endpoint
# ---------------------------------------------------------------------------

@router.get("")
async def list_documents():
    """Return stored document filenames grouped by ``subject_id``.

    Raises:
        HTTPException(503): when RAG is disabled.
    """
    _require_rag()

    db = get_client()
    result = (
        db.table("documents")
        .select("subject_id, filename")
        .execute()
    )

    # Group unique filenames by subject_id
    grouped: dict[str, list[str]] = {}
    for row in result.data or []:
        sid = row.get("subject_id") or "unknown"
        fname = row.get("filename", "")
        if fname not in grouped.get(sid, []):
            grouped.setdefault(sid, []).append(fname)

    return {"documents": grouped}
