"""pipeline.py - multi-query retrieval + rerank + grounded answer (ported logic).

Replaces legacy rag_pipeline.py. Retrieval now hits Supabase pgvector instead of
an in-process Chroma store; generation uses llama-cpp Mistral instead of Ollama.
"""
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

from langchain_core.documents import Document

from . import vector_store as vs
from .embeddings import embed_query, embed_texts
from .document_loader import load_and_split
from .reranker import rerank_documents, RERANK_K
from .llm import generate

logger = logging.getLogger(__name__)

RETRIEVER_K = int(os.environ.get("RETRIEVER_K", "8"))
MULTI_QUERY = os.environ.get("MULTI_QUERY", "true").lower() == "true"

_PROMPT_TEMPLATE = """You are a precise document analyzer. Answer ONLY based on the provided context.

CRITICAL RULES:
1. Answer ONLY from the context below - do NOT use any external knowledge
2. If information is missing, respond EXACTLY: "This information is not available in the provided document."
3. Always quote directly from the context when possible
4. Include specific page references [p. X] for each claim
5. Be detailed and comprehensive in your answer using the full context provided
6. If the question cannot be answered from the document, say so clearly

CONTEXT FROM DOCUMENT:
{context}

QUESTION: {question}

ANSWER (based strictly on the context above):"""


# ── Indexing ──────────────────────────────────────────────────────────────────

def index_document(user_id: str, document_id: str, storage_path: str) -> int:
    """Download PDF from storage, chunk, embed, write to pgvector. Returns chunk count."""
    vs.set_document_status(document_id, "indexing")
    try:
        pdf_bytes = vs.download_pdf(storage_path)
        tmp = Path(f"/tmp/{document_id}.pdf")
        tmp.write_bytes(pdf_bytes)

        chunks = load_and_split(str(tmp))
        embeddings = embed_texts([c.page_content for c in chunks])
        count = vs.insert_chunks(user_id, document_id, chunks, embeddings)

        tmp.unlink(missing_ok=True)
        vs.set_document_status(document_id, "ready")
        return count
    except Exception as exc:
        logger.exception("Indexing failed for %s", document_id)
        vs.set_document_status(document_id, "error", str(exc))
        raise


# ── Retrieval helpers ─────────────────────────────────────────────────────────

def _generate_queries(question: str) -> List[str]:
    """Ask the LLM for 3 alternative phrasings (multi-query retrieval)."""
    prompt = (
        "You are a helpful assistant that generates multiple search queries. "
        "Given a user question, generate 3 alternative phrasings of the same question "
        "that would retrieve different but relevant document sections. "
        "List each query on a new line without numbering or bullets:\n\n" + question
    )
    resp = generate(prompt, temperature=0.0)
    return [q.strip() for q in resp.split("\n") if q.strip()][:3]


def _retrieve(jwt: str, question: str, document_id: str) -> List[Document]:
    queries = [question]
    if MULTI_QUERY:
        try:
            queries.extend(_generate_queries(question))
        except Exception as e:
            logger.warning("Query expansion failed: %s", e)

    all_docs: List[Document] = []
    for q in queries:
        try:
            emb = embed_query(q)
            all_docs.extend(vs.match_chunks(jwt, emb, RETRIEVER_K, document_id))
        except Exception as e:
            logger.warning("Retrieval failed for query %r: %s", q[:60], e)
    return all_docs


def _format_docs(docs: List[Document]) -> str:
    parts = []
    for d in docs:
        page = d.metadata.get("page")
        label = f"[p. {page + 1}]" if isinstance(page, int) else "[p. ?]"
        parts.append(f"{label}\n{d.page_content.strip()}")
    return "\n\n---\n\n".join(parts)


def _extract_sources(docs: List[Document], filename: str) -> List[Dict]:
    seen, sources = set(), []
    for d in docs:
        page = d.metadata.get("page")
        page_label = (page + 1) if isinstance(page, int) else None
        key = (filename, page_label)
        if key not in seen:
            seen.add(key)
            sources.append({"filename": filename, "page": page_label})
    return sources


# ── Answering ─────────────────────────────────────────────────────────────────

def answer_question(jwt: str, question: str, document_id: str, filename: str) -> Tuple[str, List[Dict]]:
    if not question.strip():
        return "Please enter a question.", []

    docs = _retrieve(jwt, question, document_id)

    # Dedupe by content prefix.
    unique: Dict[str, Document] = {}
    for d in docs:
        unique.setdefault(d.page_content[:100], d)
    docs = rerank_documents(list(unique.values()), question, top_k=RERANK_K)

    if not docs:
        return "This information is not available in the provided document.", []

    prompt = _PROMPT_TEMPLATE.format(context=_format_docs(docs), question=question)
    answer = generate(prompt, temperature=0.1)
    sources = _extract_sources(docs, filename)
    logger.info("Answer generated (%d chars, %d sources).", len(answer), len(sources))
    return answer, sources
