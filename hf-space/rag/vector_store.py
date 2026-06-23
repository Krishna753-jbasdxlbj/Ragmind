"""vector_store.py - Supabase pgvector client (replaces ChromaDB).

Two client roles:
  - service client (SUPABASE_SERVICE_KEY): trusted writes (chunk inserts, status
    updates, storage download). Bypasses RLS, so user_id is always set explicitly.
  - user client (built per-request from the caller's JWT): retrieval via the
    match_chunks RPC, so RLS scopes results to the caller.
"""
import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional

from supabase import Client, create_client
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", SERVICE_KEY)

INSERT_BATCH = int(os.environ.get("CHUNK_INSERT_BATCH", "200"))


@lru_cache(maxsize=1)
def service_client() -> Client:
    return create_client(SUPABASE_URL, SERVICE_KEY)


def user_client(jwt: str) -> Client:
    """Per-request client that runs queries as the calling user (RLS applies)."""
    client = create_client(SUPABASE_URL, ANON_KEY)
    client.postgrest.auth(jwt)
    return client


# ── Writes (service role) ─────────────────────────────────────────────────────

def download_pdf(storage_path: str) -> bytes:
    """Fetch a PDF from the private 'documents' bucket."""
    return service_client().storage.from_("documents").download(storage_path)


def set_document_status(document_id: str, status: str, error: Optional[str] = None) -> None:
    service_client().table("documents").update(
        {"status": status, "error": error}
    ).eq("id", document_id).execute()


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
    client = service_client()
    for i in range(0, len(rows), INSERT_BATCH):
        client.table("chunks").insert(rows[i : i + INSERT_BATCH]).execute()
    logger.info("Inserted %d chunk(s) for document %s.", len(rows), document_id)
    return len(rows)


def delete_document(document_id: str, storage_path: str) -> None:
    """Hard-delete a document and its storage object.

    chunks and messages reference documents with ON DELETE CASCADE, so deleting
    the row removes them too. The storage object is not covered by the cascade and
    is removed explicitly (best-effort: a missing object must not block the row
    delete). Service role bypasses RLS; the caller is responsible for ownership.
    """
    client = service_client()
    try:
        client.storage.from_("documents").remove([storage_path])
    except Exception:
        logger.exception("Failed to remove storage object %s (continuing).", storage_path)
    client.table("documents").delete().eq("id", document_id).execute()
    logger.info("Deleted document %s.", document_id)


def insert_message(
    user_id: str,
    document_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, object]]] = None,
) -> None:
    service_client().table("messages").insert(
        {
            "user_id": user_id,
            "document_id": document_id,
            "role": role,
            "content": content,
            "sources": sources,
        }
    ).execute()


# ── Reads (user JWT, RLS-scoped) ──────────────────────────────────────────────

def match_chunks(jwt: str, query_embedding: List[float], match_count: int, doc: str) -> List[Document]:
    """Cosine similarity search via the match_chunks RPC, scoped to the caller by RLS."""
    resp = user_client(jwt).rpc(
        "match_chunks",
        {"query_embedding": query_embedding, "match_count": match_count, "doc": doc},
    ).execute()
    docs: List[Document] = []
    for row in resp.data or []:
        docs.append(
            Document(
                page_content=row["content"],
                metadata={"page": row.get("page"), "document_id": row.get("document_id")},
            )
        )
    return docs
