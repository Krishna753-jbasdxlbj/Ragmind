---
title: RAGmind API
emoji: 📄
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# RAGmind API (HF Space)

FastAPI backend for RAGmind. Runs the full RAG pipeline: PDF chunking, embeddings
(`all-MiniLM-L6-v2`), pgvector retrieval (Supabase), cross-encoder reranking, and
generation with Mistral via `llama-cpp-python`.

## Endpoints
- `GET /health`
- `POST /index` — body `{ "document_id": "..." }`, `Authorization: Bearer <supabase_jwt>`
- `POST /chat` — body `{ "document_id": "...", "question": "..." }`, Bearer JWT

## Deploy
Push this folder as the root of a **Docker** Space. Set secrets from `.env.example`
(at minimum `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`,
`SUPABASE_JWT_SECRET`). For GPU hardware, set `LLM_N_GPU_LAYERS=-1` and rebuild
`llama-cpp-python` with CUDA (see `Dockerfile`).

## Local run
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```
