# RAGmind HF Space - Docker SDK (CPU). No source compilation: everything installs
# from prebuilt wheels so the free-tier build doesn't OOM/timeout.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/data/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/data/.cache/sentence-transformers

# The abetlen prebuilt llama-cpp wheels are linked against musl libc, but this is a
# Debian (glibc) image. Install musl and expose it under the name libllama.so wants.
RUN apt-get update && apt-get install -y --no-install-recommends musl \
    && ln -sf /lib/ld-musl-x86_64.so.1 /lib/libc.musl-x86_64.so.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# 1) CPU-only PyTorch — avoids pulling ~2GB of NVIDIA CUDA wheels on a CPU Space.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2) Prebuilt CPU llama-cpp-python wheel (0.3.19 is the latest cp311 CPU wheel on the
#    abetlen index). --only-binary forces the wheel instead of building from source.
RUN pip install --no-cache-dir "llama-cpp-python==0.3.19" \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
    --only-binary llama-cpp-python

# 3) Everything else. torch + llama-cpp-python are already satisfied, so this won't
#    refetch them (and won't pull the CUDA torch build).
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces expects the app on 7860.
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
