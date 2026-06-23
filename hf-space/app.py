"""app.py - FastAPI RAG backend for Hugging Face Spaces (replaces legacy Flask).

Endpoints:
  GET  /health         - liveness + whether the LLM is warm
  POST /index          - index an already-uploaded PDF (background job)
  POST /chat           - ask a question against an indexed document

Auth: every protected route requires a Supabase Bearer JWT (see auth.py).
The frontend uploads the PDF straight to Supabase Storage, then calls /index.
"""
import logging
import os

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import AuthContext, require_auth
from rag import pipeline, vector_store as vs
from rag.embeddings import get_embedder
from rag.reranker import get_reranker
from rag.llm import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAGmind API")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    document_id: str


class ChatRequest(BaseModel):
    document_id: str
    question: str


def _get_owned_document(document_id: str, user_id: str) -> dict:
    """Fetch a document row, enforcing ownership."""
    resp = (
        vs.service_client()
        .table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found.")
    return rows[0]


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok"}


@app.post("/index")
def index(
    req: IndexRequest, background: BackgroundTasks, auth: AuthContext = Depends(require_auth)
) -> dict[str, object]:
    doc = _get_owned_document(req.document_id, auth.user_id)
    background.add_task(pipeline.index_document, auth.user_id, doc["id"], doc["storage_path"])
    return {"success": True, "status": "indexing", "document_id": doc["id"]}


@app.post("/chat")
def chat(req: ChatRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    doc = _get_owned_document(req.document_id, auth.user_id)
    if doc["status"] != "ready":
        raise HTTPException(status_code=409, detail=f"Document not ready (status: {doc['status']}).")

    answer, sources = pipeline.answer_question(
        jwt=auth.token,
        question=question,
        document_id=doc["id"],
        filename=doc["filename"],
    )
    # Persist the turn (best-effort).
    try:
        vs.insert_message(auth.user_id, doc["id"], "user", question)
        vs.insert_message(auth.user_id, doc["id"], "assistant", answer, sources)
    except Exception:
        logger.exception("Failed to persist chat turn.")

    return {"success": True, "answer": answer, "sources": sources}


@app.delete("/document/{document_id}")
def delete_document(
    document_id: str = Path(..., min_length=1),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, object]:
    doc = _get_owned_document(document_id, auth.user_id)
    vs.delete_document(doc["id"], doc["storage_path"])
    return {"success": True, "deleted": doc["id"]}


@app.on_event("startup")
def warm_models() -> None:
    """Preload embedding, reranker, and LLM so the first request isn't slow."""
    if os.environ.get("WARM_ON_START", "true").lower() == "true":
        logger.info("Warming models on startup ...")
        get_embedder()
        get_reranker()
        get_llm()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
