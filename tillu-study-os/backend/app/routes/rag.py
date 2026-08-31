"""RAG (Retrieval-Augmented Generation) routes — Phase 6.

All routes return HTTP 503 when ``RAG_ENABLED=false``.

Endpoints
---------
POST /rag/upload
    Accepts a multipart form upload (file + subject_id).
    Chunks, embeds, and stores the document.

POST /rag/search
    Embeds the query and performs pgvector cosine similarity search.
    If ``PARALLEL_MCP_ENABLED=true``, also retrieves web results.

GET /rag/documents
    Lists stored document filenames grouped by ``subject_id``.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.agents.search_agent import ingest_document, search_documents
from app.config import settings
from app.db import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_document(
    file: UploadFile,
    subject_id: str = Form(...),
):
    """Ingest a document: chunk → embed → store in ``documents`` table.

    Args:
        file: Uploaded file (PDF or plain text).
        subject_id: UUID of the subject this document belongs to.

    Returns:
        JSON with ``chunks_stored`` count and ``filename``.

    Raises:
        HTTPException(503): when RAG is disabled.
        HTTPException(400): when the file produces no usable text.
        HTTPException(415): when the MIME type is not supported.
    """
    _require_rag()

    content_type = file.content_type or ""
    if content_type not in ("text/plain", "application/pdf") and not (
        (file.filename or "").lower().endswith((".txt", ".pdf"))
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
        filename=file.filename or "unknown",
        content=content,
        content_type=content_type,
    )

    return {
        "chunks_stored": len(stored_rows),
        "filename": file.filename,
    }


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    subject_id: Optional[str] = None
    top_k: int = 5


@router.post("/search")
async def search(request: SearchRequest):
    """Search documents by semantic similarity to the query.

    If ``PARALLEL_MCP_ENABLED=true``, also fetches web results via the
    Parallel Search MCP tool and merges them into the response.

    Returns:
        JSON with ``document_chunks`` list and ``web_results`` list.
        ``web_results`` is always ``[]`` when MCP is disabled or fails.
    """
    _require_rag()

    # Document similarity search
    document_chunks = await search_documents(
        query=request.query,
        subject_id=request.subject_id,
        top_k=request.top_k,
    )

    # Optional: Parallel MCP web results
    web_results: list[dict] = []
    if settings.parallel_mcp_enabled:
        try:
            from app.providers.parallel_mcp import parallel_web_search
            web_results = await parallel_web_search(request.query, num_results=5)
        except NotImplementedError as exc:
            logger.warning("Parallel MCP stub raised NotImplementedError: %s", exc)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Parallel MCP web search failed: %s — continuing without web results", exc)

    return {
        "document_chunks": document_chunks,
        "web_results": web_results,
    }


# ---------------------------------------------------------------------------
# List documents endpoint
# ---------------------------------------------------------------------------

@router.get("/documents")
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

    # Group by subject_id
    grouped: dict[str, list[str]] = {}
    for row in (result.data or []):
        sid = row.get("subject_id") or "unknown"
        fname = row.get("filename", "")
        grouped.setdefault(sid, [])
        if fname not in grouped[sid]:
            grouped[sid].append(fname)

    return {"documents": grouped}


# ---------------------------------------------------------------------------
# Internal guard
# ---------------------------------------------------------------------------

def _require_rag() -> None:
    if not settings.rag_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG document search is disabled. "
                "Set RAG_ENABLED=true in backend/.env to enable."
            ),
        )
