"""rag_pipeline.py - Advanced RAG chain with reranking and multi-query retrieval"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from document_loader import load_and_split
from vector_store import create_vector_store

logger = logging.getLogger(__name__)

LLM_MODEL      = "mistral"
RETRIEVER_K    = 8  # Increased from 4 for more comprehensive retrieval
RERANK_K       = 4  # Keep top 4 after reranking

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

@dataclass
class RAGResponse:
    answer: str
    sources: List[str]


# ── Reranker (cross-encoder for better relevance ranking) ─────────────────────
_reranker: CrossEncoder | None = None

def get_reranker() -> CrossEncoder:
    """Lazy-load the reranker model for ranking retrieved documents."""
    global _reranker
    if _reranker is None:
        logger.info("Loading cross-encoder reranker model...")
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        logger.info("Reranker ready.")
    return _reranker


def _rerank_documents(docs: List[Document], question: str, top_k: int = RERANK_K) -> List[Document]:
    """
    Rerank documents using a cross-encoder for better relevance scoring.
    This ensures the most relevant chunks are used in the prompt.
    """
    if len(docs) <= top_k:
        return docs
    
    reranker = get_reranker()
    # Score each document-question pair
    pairs = [[question, doc.page_content] for doc in docs]
    scores = reranker.predict(pairs)
    
    # Sort by score (descending) and keep top_k
    scored_docs = list(zip(docs, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    reranked = [doc for doc, score in scored_docs[:top_k]]
    
    logger.info("Reranked %d docs → top %d by relevance", len(docs), top_k)
    return reranked

def _format_docs(docs: List[Document]) -> str:
    """Concatenate retrieved chunks with page attribution."""
    parts = []
    for doc in docs:
        page = doc.metadata.get("page", "?")
        parts.append(f"[p. {page + 1}]\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(parts)

def _extract_sources(docs: List[Document]) -> List[str]:
    """Build a de-duplicated list of source labels (filename only)."""
    seen = set()
    sources: List[str] = []
    for doc in docs:
        # ← FIXED: Extract just the filename from full temp path
        source_path = doc.metadata.get("source", "document")
        filename = Path(source_path).name  # e.g., "hp_vitus.pdf"
        
        page = doc.metadata.get("page", 0)
        label = f"{filename}, page {page + 1}"  # ← FIXED: uses filename
        
        if label not in seen:
            seen.add(label)
            sources.append(label)
    return sources

def build_rag_chain(file_path: str):
    """
    Build an advanced RAG chain with:
    - Multi-query retrieval (rephrases question for better coverage)
    - Reranking (scores chunks by relevance)
    - Enhanced prompting (enforces document grounding)
    """
    logger.info("Building advanced RAG chain for: %s", file_path)
    
    chunks = load_and_split(file_path)
    vector_store = create_vector_store(chunks)
    base_retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVER_K})
    
    # Create query expansion LLM for generating alternatives
    query_expansion_llm = OllamaLLM(model=LLM_MODEL, temperature=0)
    answer_llm = OllamaLLM(model=LLM_MODEL, temperature=0.1)
    
    prompt = PromptTemplate.from_template(_PROMPT_TEMPLATE)

    def _generate_queries(question: str) -> List[str]:
        """Generate alternative phrasings of the question."""
        query_prompt = PromptTemplate.from_template(
            "You are a helpful assistant that generates multiple search queries. "
            "Given a user question, generate 3 alternative phrasings of the same question "
            "that would retrieve different but relevant document sections. "
            "List each query on a new line without numbering or bullets:\n\n{question}"
        )
        chain = query_prompt | query_expansion_llm | StrOutputParser()
        response = chain.invoke({"question": question})
        # Parse response into list of queries
        queries = [q.strip() for q in response.split('\n') if q.strip()]
        return queries[:3]  # Keep only first 3

    def _multi_query_retrieve(question: str) -> List[Document]:
        """Retrieve docs using multiple query variations."""
        queries = [question]  # Include original
        try:
            # Try to generate alternatives
            alt_queries = _generate_queries(question)
            queries.extend(alt_queries)
        except Exception as e:
            logger.warning("Failed to generate query variations: %s", e)
        
        # Retrieve docs from all queries
        all_docs = []
        for q in queries:
            try:
                docs = base_retriever.invoke(q)
                all_docs.extend(docs)
            except Exception as e:
                logger.warning("Failed to retrieve for query '%s': %s", q, e)
        
        return all_docs

    def _build_inputs(question: str):
        """Retrieve docs, rerank them, and format context."""
        # Get docs from multi-query retrieval
        docs = _multi_query_retrieve(question)
        
        # Deduplicate and rerank
        unique_docs = {}
        for doc in docs:
            key = doc.page_content[:100]  # Use first 100 chars as key
            if key not in unique_docs:
                unique_docs[key] = doc
        docs = list(unique_docs.values())
        
        # Rerank to get most relevant chunks
        docs = _rerank_documents(docs, question, top_k=RERANK_K)
        
        return {
            "context": _format_docs(docs),
            "question": question,
            "_docs": docs,
        }

    answer_chain = (
        RunnableLambda(_build_inputs)
        | {
            "answer": (
                RunnableLambda(lambda x: {"context": x["context"], "question": x["question"]})
                | prompt | answer_llm | StrOutputParser()
            ),
            "_docs": RunnableLambda(lambda x: x["_docs"]),
        }
    )
    logger.info("Advanced RAG chain ready (model=%s, retriever_k=%d, rerank_k=%d).", 
                LLM_MODEL, RETRIEVER_K, RERANK_K)
    return answer_chain

def ask_question(chain, question: str) -> Tuple[str, List[str]]:
    """Run question through chain and return (answer, sources)."""
    if not question.strip():
        return "Please enter a question.", []
    
    logger.info("Processing question: %r", question[:80])
    result = chain.invoke(question)
    answer = result["answer"]
    sources = _extract_sources(result["_docs"])
    logger.info("Answer generated (%d chars, %d sources).", len(answer), len(sources))
    return answer, sources