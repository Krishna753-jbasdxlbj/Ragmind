"""vector_store.py - Supabase pgvector client (replaces ChromaDB).

Two client roles:
  - service client (SUPABASE_SERVICE_KEY): trusted writes (chunk inserts, status
    updates, storage download). Bypasses RLS, so user_id is always set explicitly.
  - user client (built per-request from the caller's JWT): retrieval via the
    match_chunks RPC, so RLS scopes results to the caller.

Resilience: postgrest talks to Supabase over HTTP/2 and reuses connections.
Supabase periodically closes idle connections (GOAWAY), so a reused client can
raise httpx.RemoteProtocolError on the next call — this was silently killing the
background indexing task. Every call is wrapped in a retry that drops the stale
client and rebuilds a fresh one.
"""
import logging
import os
from typing import Callable, Dict, List, Optional

import httpx
from supabase import Client, create_client
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", SERVICE_KEY)

INSERT_BATCH = int(os.environ.get("CHUNK_INSERT_BATCH", "200"))
DB_RETRIES = int(os.environ.get("DB_RETRIES", "3"))

# Connection-level errors worth retrying on a fresh client.
_TRANSIENT = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
)

_service: Optional[Client] = None


def service_client() -> Client:
    global _service
    if _service is None:
        _service = create_client(SUPABASE_URL, SERVICE_KEY)
    return _service


def _reset_service() -> None:
    global _service
    _service = None


def _with_service(fn: Callable[[Client], object]):
    """Run fn(service_client()) with retry; rebuild the client on stale-connection errors."""
    last: Optional[Exception] = None
    for attempt in range(DB_RETRIES):
        try:
            return fn(service_client())
        except _TRANSIENT as e:
            last = e
            logger.warning("Transient Supabase error (attempt %d/%d): %s — rebuilding client.",
                           attempt + 1, DB_RETRIES, e)
            _reset_service()
    raise last  # type: ignore[misc]


def user_client(jwt: str) -> Client:
    """Per-request client that runs queries as the calling user (RLS applies)."""
    client = create_client(SUPABASE_URL, ANON_KEY)
    client.postgrest.auth(jwt)
    return client


# ── Reads / writes (service role) ─────────────────────────────────────────────

def get_owned_document(document_id: str, user_id: str) -> Optional[dict]:
    """Fetch a document row scoped to its owner, or None."""
    resp = _with_service(
        lambda c: c.table("documents").select("*").eq("id", document_id).eq("user_id", user_id).limit(1).execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def download_pdf(storage_path: str) -> bytes:
    """Fetch a PDF from the private 'documents' bucket."""
    return _with_service(lambda c: c.storage.from_("documents").download(storage_path))


def set_document_status(document_id: str, status: str, error: Optional[str] = None) -> None:
    _with_service(
        lambda c: c.table("documents").update({"status": status, "error": error}).eq("id", document_id).execute()
    )


def insert_chunks(
    user_id: str,
    document_id: str,
    docs: List[Document],
    embeddings: List[List[float]],
) -> int:
    """Insert chunk rows with embeddings. user_id set explicitly (service role bypasses RLS)."""
    rows = [
        {
            "user_id": user_id,
            "document_id": document_id,
            "content": d.page_content,
            "page": d.metadata.get("page"),
            "embedding": emb,
        }
        for d, emb in zip(docs, embeddings)
    ]
    for i in range(0, len(rows), INSERT_BATCH):
        batch = rows[i : i + INSERT_BATCH]
        _with_service(lambda c, b=batch: c.table("chunks").insert(b).execute())
    logger.info("Inserted %d chunk(s) for document %s.", len(rows), document_id)
    return len(rows)


def delete_document(document_id: str, storage_path: str) -> None:
    """Hard-delete a document and its storage object.

    chunks and messages reference documents with ON DELETE CASCADE, so deleting
    the row removes them too. The storage object is removed explicitly
    (best-effort: a missing object must not block the row delete).
    """
    try:
        _with_service(lambda c: c.storage.from_("documents").remove([storage_path]))
    except Exception:
        logger.exception("Failed to remove storage object %s (continuing).", storage_path)
    _with_service(lambda c: c.table("documents").delete().eq("id", document_id).execute())
    logger.info("Deleted document %s.", document_id)


def insert_message(
    user_id: str,
    document_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, object]]] = None,
) -> None:
    _with_service(
        lambda c: c.table("messages").insert(
            {"user_id": user_id, "document_id": document_id, "role": role, "content": content, "sources": sources}
        ).execute()
    )


# ── Reads (user JWT, RLS-scoped) ──────────────────────────────────────────────

def match_chunks(jwt: str, query_embedding: List[float], match_count: int, doc: str) -> List[Document]:
    """Cosine similarity search via the match_chunks RPC, scoped to the caller by RLS."""
    last: Optional[Exception] = None
    for attempt in range(DB_RETRIES):
        try:
            resp = user_client(jwt).rpc(
                "match_chunks",
                {"query_embedding": query_embedding, "match_count": match_count, "doc": doc},
            ).execute()
            return [
                Document(
                    page_content=row["content"],
                    metadata={"page": row.get("page"), "document_id": row.get("document_id")},
                )
                for row in (resp.data or [])
            ]
        except _TRANSIENT as e:
            last = e
            logger.warning("Transient Supabase error in match_chunks (attempt %d/%d): %s.",
                           attempt + 1, DB_RETRIES, e)
    raise last  # type: ignore[misc]
