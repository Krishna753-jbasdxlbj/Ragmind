# RAGmind HF Space - Docker SDK (CPU build).
# For a GPU Space, switch the base image to an nvidia/cuda runtime and rebuild
# llama-cpp-python with: CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/data/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/data/.cache/sentence-transformers

# Build tools for llama-cpp-python + sentence-transformers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# Install llama-cpp-python from the prebuilt CPU wheel index (no source compile —
# avoids OOM/timeout on small build hosts). Other deps resolve from PyPI.
RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

COPY . .

# HF Spaces expects the app on 7860.
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
