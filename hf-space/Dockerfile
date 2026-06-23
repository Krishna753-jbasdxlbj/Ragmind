# RAGmind HF Space - Docker SDK (CPU). Self-hosted model (private). All wheels
# prebuilt — no source compilation, so the free-tier build is quick and reliable.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/data/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/data/.cache/sentence-transformers

# The abetlen prebuilt llama-cpp wheels link against musl libc; this is a Debian
# (glibc) image, so install musl and expose it under the name libllama.so wants.
RUN apt-get update && apt-get install -y --no-install-recommends musl \
    && ln -sf /lib/ld-musl-x86_64.so.1 /lib/libc.musl-x86_64.so.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# CPU-only PyTorch (embeddings + cross-encoder reranker). Avoids ~2GB CUDA wheels.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Prebuilt CPU llama-cpp-python wheel — --only-binary forces the wheel, never compiles.
RUN pip install --no-cache-dir "llama-cpp-python==0.3.19" \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
    --only-binary llama-cpp-python

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
