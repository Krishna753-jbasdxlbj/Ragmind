"""reranker.py - cross-encoder reranking (ported from legacy)."""
import logging
import os
from functools import lru_cache
from typing import List

from sentence_transformers import CrossEncoder
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

RERANK_MODEL = os.environ.get("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_K = int(os.environ.get("RERANK_K", "4"))


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    logger.info("Loading cross-encoder reranker '%s' ...", RERANK_MODEL)
    model = CrossEncoder(RERANK_MODEL)
    logger.info("Reranker ready.")
    return model


def rerank_documents(docs: List[Document], question: str, top_k: int = RERANK_K) -> List[Document]:
    """Score doc/question pairs with the cross-encoder; keep the top_k."""
    if len(docs) <= top_k:
        return docs
    reranker = get_reranker()
    pairs = [[question, d.page_content] for d in docs]
    scores = reranker.predict(pairs)
    scored = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    reranked = [d for d, _ in scored[:top_k]]
    logger.info("Reranked %d docs -> top %d.", len(docs), top_k)
    return reranked
