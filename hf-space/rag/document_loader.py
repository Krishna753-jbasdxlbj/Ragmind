"""document_loader.py - PDF load + chunking (ported from legacy, unchanged behavior)."""
import logging
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def load_and_split(file_path: str) -> List[Document]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    logger.info("Loading PDF: %s", path.name)
    loader = PyPDFLoader(str(path))
    pages: List[Document] = loader.load()
    if not pages:
        raise ValueError("The PDF appears to be empty or unreadable.")
    logger.info("Loaded %d page(s) from '%s'", len(pages), path.name)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks: List[Document] = splitter.split_documents(pages)
    if not chunks:
        raise ValueError("Text splitting produced no chunks.")

    logger.info("Split into %d chunk(s) (size=%d, overlap=%d)", len(chunks), CHUNK_SIZE, CHUNK_OVERLAP)
    return chunks
