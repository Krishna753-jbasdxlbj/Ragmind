-- RAGmind initial schema
-- pgvector store (replaces ChromaDB) + per-user docs/chat + RLS.
-- Embedding model: sentence-transformers/all-MiniLM-L6-v2 => 384 dims (load-bearing).

create extension if not exists vector with schema extensions;

-- ── Tables ──────────────────────────────────────────────────────────────────

create table if not exists public.documents (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  filename     text not null,
  storage_path text not null,            -- path inside the 'documents' storage bucket
  status       text not null default 'pending'
               check (status in ('pending','indexing','ready','error')),
  error        text,
  created_at   timestamptz not null default now()
);

create table if not exists public.chunks (
  id          uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  content     text not null,
  page        int,
  embedding   extensions.vector(384) not null
);

create table if not exists public.messages (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  document_id uuid references public.documents(id) on delete cascade,
  role        text not null check (role in ('user','assistant')),
  content     text not null,
  sources     jsonb,                     -- [{filename, page}] for assistant turns
  created_at  timestamptz not null default now()
);

-- ── Indexes ─────────────────────────────────────────────────────────────────

create index if not exists chunks_document_id_idx on public.chunks (document_id);
create index if not exists chunks_user_id_idx      on public.chunks (user_id);
create index if not exists documents_user_id_idx   on public.documents (user_id);
create index if not exists messages_user_doc_idx   on public.messages (user_id, document_id, created_at);

-- Approximate nearest-neighbour index for cosine similarity.
-- ivfflat needs ANALYZE after data load; lists tuned for small/medium corpora.
create index if not exists chunks_embedding_idx
  on public.chunks using ivfflat (embedding extensions.vector_cosine_ops)
  with (lists = 100);

-- ── Row Level Security ──────────────────────────────────────────────────────

alter table public.documents enable row level security;
alter table public.chunks    enable row level security;
alter table public.messages  enable row level security;

-- documents
create policy "documents_select_own" on public.documents
  for select using (auth.uid() = user_id);
create policy "documents_insert_own" on public.documents
  for insert with check (auth.uid() = user_id);
create policy "documents_update_own" on public.documents
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "documents_delete_own" on public.documents
  for delete using (auth.uid() = user_id);

-- chunks (written by the HF Space; reads scoped by RLS)
create policy "chunks_select_own" on public.chunks
  for select using (auth.uid() = user_id);
create policy "chunks_insert_own" on public.chunks
  for insert with check (auth.uid() = user_id);
create policy "chunks_delete_own" on public.chunks
  for delete using (auth.uid() = user_id);

-- messages
create policy "messages_select_own" on public.messages
  for select using (auth.uid() = user_id);
create policy "messages_insert_own" on public.messages
  for insert with check (auth.uid() = user_id);
create policy "messages_delete_own" on public.messages
  for delete using (auth.uid() = user_id);

-- NOTE: the service-role key bypasses RLS. The HF Space may use it for trusted
-- writes (chunk inserts) but must always set user_id explicitly to the owner.

-- ── Similarity search RPC ───────────────────────────────────────────────────
-- Called from the HF Space with the user's JWT so RLS scopes results to the
-- caller. `doc` optionally restricts to one document. Returns cosine distance
-- as `distance` (smaller = closer).

create or replace function public.match_chunks(
  query_embedding extensions.vector(384),
  match_count     int default 8,
  doc             uuid default null
)
returns table (
  id          uuid,
  document_id uuid,
  content     text,
  page        int,
  distance    float
)
language sql
stable
security invoker            -- run as caller => RLS applies
set search_path = public, extensions
as $$
  select c.id,
         c.document_id,
         c.content,
         c.page,
         (c.embedding <=> query_embedding) as distance
  from public.chunks c
  where doc is null or c.document_id = doc
  order by c.embedding <=> query_embedding
  limit match_count;
$$;
