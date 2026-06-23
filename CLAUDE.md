# CLAUDE.md — RAGmind

Deployment-ready RAG platform. Upload PDFs, chat with them, answers cite pages.

> **Status:** Mid-restructure. The repo root currently holds the **legacy local
> Flask app** (`app.py`, `rag_pipeline.py`, `vector_store.py`, `document_loader.py`,
> ChromaDB, Ollama). We are migrating it to the **target architecture** below.
> When writing new code, build toward the target — do not extend the legacy app.

---

## Target architecture

Three deployable pieces. The frontend talks to **both** the HF Space (RAG compute)
and Supabase (auth/data/storage).

```
┌─────────────────────────────┐
│  Frontend (React+Vite+TS)   │  Claude design aesthetic
│  - Supabase Auth (login)    │  Vercel / static host
│  - upload PDF, chat UI      │
└───────┬──────────────┬──────┘
        │ JWT          │ JWT + question
        ▼              ▼
┌───────────────┐   ┌──────────────────────────────┐
│   Supabase    │   │   HF Space (FastAPI, Docker)  │
│  - Auth (JWT) │◀──│  full RAG pipeline:           │
│  - Storage    │   │   chunk → embed → retrieve    │
│  - Postgres   │   │   → rerank → LLM → cite       │
│    + pgvector │──▶│  llama-cpp-python (Mistral)   │
│  - RLS        │   │  reads/writes Supabase pgvec  │
└───────────────┘   └──────────────────────────────┘
```

### Components

| Piece | Stack | Deploys to | Replaces |
|---|---|---|---|
| **frontend/** | React + Vite + TypeScript, Claude design | Vercel / Netlify (static) | legacy `templates/` + `static/` |
| **hf-space/** | FastAPI + Python, Docker | Hugging Face Spaces | legacy `app.py` (Flask) |
| **supabase/** | Postgres + pgvector + Auth + Storage + RLS | Supabase cloud | ChromaDB local store |

### Model

- **LLM:** `bartowski/Mistral-7B-Instruct-v0.3-GGUF`, file
  `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf`, run via **`llama-cpp-python`**.
  Replaces Ollama Mistral. Loaded **once** per process via `functools.lru_cache`
  (or module singleton) on the HF Space. Downloaded with `huggingface_hub`
  `hf_hub_download` at startup; cache to the Space's persistent dir.
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` → **384-dim** vectors
  (pgvector column must be `vector(384)`).
- **Reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (kept; runs on the Space).
- Model id / filename / `n_ctx` / `n_gpu_layers` should be **env vars**, not hardcoded.

---

## Data flow

**Upload / index** (`POST /index` on the Space)
1. Frontend uploads the PDF to **Supabase Storage** (bucket scoped to the user).
2. Frontend calls the Space `/index` with the storage path + the user's Supabase JWT.
3. Space verifies the JWT → `user_id`, downloads the PDF, `load_and_split` → chunks.
4. Space embeds chunks (`all-MiniLM-L6-v2`) and **inserts rows into Supabase
   `chunks`** (content + `vector(384)` + page + `document_id` + `user_id`).

**Chat** (`POST /chat` on the Space)
1. Frontend sends `{ question, document_id }` + JWT.
2. Space: multi-query expand → embed each query → **pgvector similarity search**
   via a Postgres RPC (`match_chunks`) scoped to the user/doc → dedupe → rerank
   (cross-encoder, top-k) → format context with `[p. N]` → Mistral (llama-cpp) →
   answer + deduped sources.
3. Space persists the turn to Supabase `messages` (chat history per user).

**Auth model:** Supabase Auth issues the JWT. The Space verifies it with the
Supabase JWT secret to derive `user_id`, then either (a) calls PostgREST/RPC with
the user JWT so **RLS** enforces scoping, or (b) uses the service-role key and
filters by `user_id` explicitly. Prefer (a) for reads, (b) only for trusted writes.
Never ship the service-role key to the frontend.

---

## Proposed repo layout (target)

```
Ragmind/
├── CLAUDE.md                  # this file
├── README.md                  # (legacy marketing copy; update later)
├── frontend/                  # React + Vite + TS, Claude design
│   ├── src/
│   │   ├── lib/supabase.ts    # Supabase client (anon key)
│   │   ├── api/rag.ts         # fetch wrappers → HF Space /index, /chat
│   │   ├── components/        # Upload, Chat, MessageList, SourceChip, Auth…
│   │   ├── pages/             # Login, App
│   │   └── main.tsx
│   ├── .env.example           # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_HF_SPACE_URL
│   └── package.json
├── hf-space/                  # FastAPI app for HF Spaces (Docker)
│   ├── app.py                 # FastAPI: /health, /index, /chat
│   ├── rag/
│   │   ├── document_loader.py # port of legacy (PyPDF + RecursiveCharacterTextSplitter)
│   │   ├── embeddings.py      # all-MiniLM-L6-v2 singleton
│   │   ├── reranker.py        # cross-encoder singleton
│   │   ├── llm.py             # llama-cpp-python, lru_cache, GGUF download
│   │   ├── vector_store.py    # Supabase pgvector client (REPLACES Chroma)
│   │   └── pipeline.py        # multi-query retrieve + rerank + prompt + answer
│   ├── auth.py                # verify Supabase JWT → user_id
│   ├── requirements.txt
│   ├── Dockerfile             # HF Spaces Docker SDK, expose 7860
│   └── .env.example           # SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET, LLM_*, HF_TOKEN
└── supabase/
    ├── config.toml
    └── migrations/            # pgvector ext, tables, RLS, match_chunks RPC
```

Migration mapping from legacy:
- `document_loader.py` → `hf-space/rag/document_loader.py` (mostly as-is).
- `vector_store.py` (Chroma) → **rewrite** as `hf-space/rag/vector_store.py`
  talking to Supabase pgvector (insert chunks, `match_chunks` RPC). Embedding model
  unchanged.
- `rag_pipeline.py` → split into `embeddings.py` + `reranker.py` + `llm.py` +
  `pipeline.py`. Swap `OllamaLLM` → llama-cpp-python wrapper. Keep multi-query +
  rerank + the strict grounding prompt.
- `app.py` (Flask) → `hf-space/app.py` (FastAPI). In-memory single `_rag_chain`
  becomes per-user, per-document via Supabase. Drop the global chain singleton.
- `templates/` + `static/` → replaced by `frontend/`.

---

## Supabase schema (target sketch)

```sql
create extension if not exists vector;

create table documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  filename text not null,
  storage_path text not null,
  created_at timestamptz default now()
);

create table chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  user_id uuid not null references auth.users(id),
  content text not null,
  page int,
  embedding vector(384)            -- all-MiniLM-L6-v2
);
create index on chunks using ivfflat (embedding vector_cosine_ops);

create table messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  document_id uuid references documents(id) on delete cascade,
  role text check (role in ('user','assistant')),
  content text not null,
  sources jsonb,
  created_at timestamptz default now()
);
```

- **RLS on every table**: `user_id = auth.uid()`.
- `match_chunks(query_embedding vector(384), match_count int, doc uuid)` RPC:
  cosine similarity, filtered by `user_id = auth.uid()` and `document_id`.

---

## Commands (target — once dirs exist)

```bash
# Frontend
cd frontend && npm install
npm run dev          # http://localhost:5173
npm run build

# HF Space (local)
cd hf-space && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860 --reload

# Supabase
supabase start                 # local stack
supabase db push               # apply migrations
supabase functions ...         # if any edge fns added later
```

**Legacy (still runnable until migrated):**
```bash
pip install -r requirements.txt
python app.py        # Flask on :7860, needs local Ollama + Chroma
```

---

## Conventions

- **Secrets:** anon key + URL only in the frontend (`VITE_*`). Service-role key and
  `SUPABASE_JWT_SECRET` only on the HF Space. Never commit `.env`; keep `.env.example`.
- **Embedding dim is load-bearing:** 384. If the embedding model changes, the
  pgvector column and index must change too.
- **Model config via env**, never hardcoded (model repo, gguf filename, `n_ctx`,
  `n_gpu_layers`, temperature).
- **Grounding prompt** (answer only from context, cite `[p. N]`, refuse if missing)
  is product behavior — preserve it when porting.
- Keep the singleton pattern for heavy models (embeddings, reranker, llama-cpp) so
  they load once per Space process.
- Per-user isolation is mandatory (RLS + JWT). No global shared state like the
  legacy `_rag_chain`.

---

## Deploy targets

- **Frontend:** Vercel/Netlify static build. Set `VITE_*` env in the host.
- **HF Space:** Docker SDK Space. `Dockerfile` installs `llama-cpp-python`
  (CPU or CUDA depending on Space hardware), downloads the GGUF at build/startup,
  runs `uvicorn` on `7860`. Space secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
  `SUPABASE_JWT_SECRET`, `HF_TOKEN`, `LLM_*`.
- **Supabase:** cloud project; run migrations; create the Storage bucket; enable RLS.

---

## Open items to resolve during build

- HF Space hardware tier (CPU vs GPU) — drives `llama-cpp-python` build flags and
  latency. Q4_K_M 7B is CPU-runnable but slow; confirm tier.
- Whether the Space writes pgvector directly (service key) or proxies through a
  Supabase edge function. Default: Space writes directly with service key, reads via
  RLS-scoped RPC.
- CORS: Space must allow the frontend origin.
