"""embeddings.py - all-MiniLM-L6-v2 embeddings (384-dim, cosine-normalized)."""
import logging
import os
from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # load-bearing: must match pgvector vector(384)


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    logger.info("Loading embedding model '%s' ...", EMBEDDING_MODEL)
    model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info("Embedding model ready (dim=%d).", model.get_sentence_embedding_dimension())
    return model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed many texts. Normalized so pgvector cosine distance is meaningful."""
    model = get_embedder()
    vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
