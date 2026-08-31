"""RAG Search Agent — document ingestion and vector similarity search.

Phase 6 feature: gated behind ``RAG_ENABLED=true``.

Responsibilities:
  1. Chunk plain-text or PDF content into overlapping segments.
  2. Embed chunks using sentence-transformers (``all-MiniLM-L6-v2``, 384 dims).
     Falls back to a deterministic hash-based vector when the library is absent.
  3. Persist all chunks + embeddings to the ``documents`` table in Supabase.
  4. Perform cosine-similarity search via the ``match_documents`` Postgres RPC.

All public functions raise ``HTTPException(503)`` when RAG is disabled.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from fastapi import HTTPException

from app.config import settings
from app.db import get_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding back-end selection (loaded lazily on first use)
# ---------------------------------------------------------------------------

_st_model = None          # SentenceTransformer instance, or None if unavailable
_st_checked = False       # whether we have already attempted to load the model


def _get_st_model():
    """Return a SentenceTransformer model, or None if the library is missing."""
    global _st_model, _st_checked
    if _st_checked:
        return _st_model
    _st_checked = True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("sentence-transformers model loaded (all-MiniLM-L6-v2).")
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "sentence-transformers not available (%s). "
            "Using hash-based fallback embeddings (testing only).",
            exc,
        )
        _st_model = None
    return _st_model


# ---------------------------------------------------------------------------
# Fallback embedding — deterministic, for testing without GPU/library
# ---------------------------------------------------------------------------

def _fallback_embed(text: str) -> list[float]:
    """Deterministic 384-dim vector derived from text SHA-256 hash.

    NOTE: This produces semantically meaningless vectors.
    It exists *only* so the ingestion/search pipeline can be exercised
    in environments without sentence-transformers installed.
    """
    digest = hashlib.sha256(text.encode()).hexdigest()
    seed = int(digest, 16)
    return [((seed >> i) & 0xFF) / 255.0 for i in range(384)]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split ``text`` into overlapping character-level windows.

    Args:
        text: Source text to split.
        chunk_size: Target characters per chunk.
        overlap: Characters shared between consecutive chunks.

    Returns:
        List of non-empty chunk strings; returns ``[text]`` when text is
        shorter than ``chunk_size``.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    step = chunk_size - overlap
    if step <= 0:
        step = 1

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of text chunks.

    Resolution order:
    1. If ``settings.embedding_api_url`` is set, POST to that external API.
    2. Otherwise use ``sentence-transformers`` when available.
    3. Finally fall back to the deterministic hash-based stub.

    Args:
        chunks: List of text strings to embed.

    Returns:
        List of 384-dimensional float vectors, one per chunk.
    """
    # --- Option 1: external embedding API ---
    if settings.embedding_api_url:
        try:
            import httpx
            response = httpx.post(
                settings.embedding_api_url,
                json={"texts": chunks},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings") or data.get("data")
            if embeddings and len(embeddings) == len(chunks):
                return [list(map(float, v)) for v in embeddings]
            logger.warning(
                "Embedding API returned unexpected shape; falling back to local model."
            )
        except Exception as exc:
            logger.warning(
                "Embedding API call failed: %s — falling back to local model.", exc
            )

    # --- Option 2: local sentence-transformers ---
    model = _get_st_model()

    if model is not None:
        try:
            raw = model.encode(chunks, normalize_embeddings=True)
            return [vec.tolist() for vec in raw]
        except Exception as exc:  # pragma: no cover
            logger.warning("SentenceTransformer encode failed: %s — using fallback", exc)

    # --- Option 3: hash-based stub ---
    return [_fallback_embed(chunk) for chunk in chunks]


async def ingest_document(
    subject_id: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> list[dict]:
    """Chunk, embed, and store a document.

    Supports plain text (``text/plain``) and PDF (``application/pdf``).
    For PDF files, attempts text extraction with ``pdfminer``; if that library
    is unavailable the raw bytes are decoded as UTF-8 with errors replaced.

    Args:
        subject_id: UUID of the subject this document belongs to.
        filename: Original filename (stored for display purposes).
        content: Raw file bytes.
        content_type: MIME type from the upload (e.g. ``text/plain``).

    Returns:
        List of row dicts inserted into the ``documents`` table.

    Raises:
        HTTPException(503): when RAG is disabled.
        HTTPException(400): when text extraction produces no usable content.
    """
    _require_rag()

    # ---- Extract text -------------------------------------------------------
    text = _extract_text(content, content_type, filename)
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any text from the uploaded file.",
        )

    # ---- Chunk ---------------------------------------------------------------
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Document produced no usable text chunks.",
        )

    # ---- Embed ---------------------------------------------------------------
    embeddings = embed_chunks(chunks)

    # ---- Persist -------------------------------------------------------------
    db = get_client()
    rows = [
        {
            "subject_id": subject_id,
            "filename": filename,
            "chunk_text": chunk,
            "embedding": json.dumps(embedding),   # Supabase expects JSON array string for vector
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]

    result = db.table("documents").insert(rows).execute()
    logger.info(
        "Ingested %d chunks from '%s' (subject=%s).",
        len(rows),
        filename,
        subject_id,
    )
    return result.data


async def search_documents(
    query: str,
    subject_id: Optional[str] = None,
    top_k: int = 5,
) -> list[dict]:
    """Search documents by cosine similarity to the query embedding.

    Calls the ``match_documents`` Postgres RPC (created by migration
    ``003_rag_rpc.sql``) which performs a pgvector ``<=>`` cosine search.

    Args:
        query: Natural-language query string.
        subject_id: Optional UUID to restrict search to a single subject.
        top_k: Number of top-matching chunks to return (default 5).

    Returns:
        List of dicts with keys ``chunk_text``, ``filename``,
        ``subject_id``, and ``similarity``.

    Raises:
        HTTPException(503): when RAG is disabled.
    """
    _require_rag()

    query_embedding = embed_chunks([query])[0]

    db = get_client()
    params: dict = {
        "query_embedding": query_embedding,
        "match_count": top_k,
    }
    if subject_id:
        params["filter_subject_id"] = subject_id

    try:
        result = db.rpc("match_documents", params).execute()
    except Exception as exc:
        logger.error("match_documents RPC failed: %s", exc)
        return []

    return result.data or []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_rag() -> None:
    """Raise HTTP 503 when RAG is disabled via feature flag."""
    if not settings.rag_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG document search is disabled. "
                "Set RAG_ENABLED=true in backend/.env to enable."
            ),
        )


def _extract_text(content: bytes, content_type: str, filename: str) -> str:
    """Extract plain text from file bytes.

    Tries ``pdfminer.high_level.extract_text`` for PDF files; falls back to
    UTF-8 decode (with replacement) for all other types.
    """
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            from io import BytesIO
            from pdfminer.high_level import extract_text as pdf_extract  # type: ignore
            return pdf_extract(BytesIO(content))
        except ImportError:
            logger.warning(
                "pdfminer not installed; decoding PDF bytes as UTF-8 (lossy)."
            )
        except Exception as exc:
            logger.warning("PDF text extraction failed: %s — falling back to UTF-8", exc)

    return content.decode("utf-8", errors="replace")
