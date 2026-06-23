"""llm.py - text generation via Groq (OpenAI-compatible, fast).

Replaces local llama-cpp Mistral, which was far too slow on a free CPU Space.
Groq serves Llama/Mistral models at sub-second latency. Configure with:
  GROQ_API_KEY   (required)
  GROQ_MODEL     (default: llama-3.1-8b-instant — fastest; use a 70b model for quality)
  GROQ_BASE_URL  (default: https://api.groq.com/openai/v1)
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "60"))


def generate(prompt: str, temperature: float = 0.1, max_tokens: int = LLM_MAX_TOKENS) -> str:
    """Single-turn completion via Groq chat completions."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set on the Space.")
    resp = httpx.post(
        f"{GROQ_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
