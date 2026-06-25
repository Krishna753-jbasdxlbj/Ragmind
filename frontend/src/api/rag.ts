// Client for the HF Space RAG backend. Every call carries the Supabase JWT.
import { supabase } from "../lib/supabase";

// Calls go to the same-origin Vercel proxy (/api/*), which forwards to the
// private HF Space with the HF gating token. See frontend/api/proxy.ts.
const BASE = "/api";

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated.");
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

async function handle(res: Response) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Kick off indexing of an already-uploaded document. */
export async function indexDocument(documentId: string): Promise<void> {
  const res = await fetch(`${BASE}/index`, {
    method: "POST",
    headers: await authHeader(),
    body: JSON.stringify({ document_id: documentId }),
  });
  await handle(res);
}

/** Permanently delete a document (storage object, chunks, messages, row). */
export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${BASE}/document/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    headers: await authHeader(),
  });
  await handle(res);
}

/** Enqueue a question. Generation runs in the background on the Space; the
 *  assistant reply is written to the `messages` table and the UI polls for it.
 *  (CPU generation can exceed the serverless proxy timeout, so we don't block.) */
export async function chat(documentId: string, question: string): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: await authHeader(),
    body: JSON.stringify({ document_id: documentId, question }),
  });
  await handle(res);
}
