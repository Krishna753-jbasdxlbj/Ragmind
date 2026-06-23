"""llm.py - Mistral via llama-cpp-python (replaces Ollama).

Model: bartowski/Mistral-7B-Instruct-v0.3-GGUF / Mistral-7B-Instruct-v0.3-Q4_K_M.gguf
Loaded once per process via lru_cache. GGUF downloaded with huggingface_hub.
All knobs are env vars.
"""
import logging
import os
from functools import lru_cache

from huggingface_hub import hf_hub_download
from llama_cpp import Llama

logger = logging.getLogger(__name__)

LLM_REPO = os.environ.get("LLM_REPO", "bartowski/Mistral-7B-Instruct-v0.3-GGUF")
LLM_FILE = os.environ.get("LLM_FILE", "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf")
LLM_N_CTX = int(os.environ.get("LLM_N_CTX", "8192"))
LLM_N_GPU_LAYERS = int(os.environ.get("LLM_N_GPU_LAYERS", "0"))  # 0 = CPU; -1 = all on GPU
LLM_N_THREADS = int(os.environ.get("LLM_N_THREADS", str(os.cpu_count() or 4)))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))


@lru_cache(maxsize=1)
def get_llm() -> Llama:
    logger.info("Downloading GGUF %s / %s ...", LLM_REPO, LLM_FILE)
    model_path = hf_hub_download(
        repo_id=LLM_REPO,
        filename=LLM_FILE,
        token=os.environ.get("HF_TOKEN"),
    )
    logger.info("Loading llama.cpp model (n_ctx=%d, n_gpu_layers=%d) ...", LLM_N_CTX, LLM_N_GPU_LAYERS)
    llm = Llama(
        model_path=model_path,
        n_ctx=LLM_N_CTX,
        n_gpu_layers=LLM_N_GPU_LAYERS,
        n_threads=LLM_N_THREADS,
        verbose=False,
    )
    logger.info("LLM ready.")
    return llm


def generate(prompt: str, temperature: float = 0.1, max_tokens: int = LLM_MAX_TOKENS) -> str:
    """Run a single-turn instruction through Mistral's [INST] format."""
    llm = get_llm()
    out = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return out["choices"][0]["message"]["content"].strip()
