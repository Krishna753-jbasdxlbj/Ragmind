# RAGmind HF Space - Docker SDK (CPU). Generation runs on Groq, so there's no
# llama-cpp build here — only prebuilt wheels. Fast, reliable build.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/data/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/data/.cache/sentence-transformers

WORKDIR /app
COPY requirements.txt .

# CPU-only PyTorch (needed by sentence-transformers for embeddings + the
# cross-encoder reranker). Avoids pulling ~2GB of NVIDIA CUDA wheels.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces expects the app on 7860.
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
