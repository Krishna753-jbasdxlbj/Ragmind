// Client for the HF Space RAG backend. Every call carries the Supabase JWT.
import { supabase } from "../lib/supabase";
import type { Source } from "../types";

// Calls go to the same-origin Vercel proxy (/api/*), which forwards to the
// private HF Space with the HF gating token. See frontend/api/[...path].ts.
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

/** Ask a question against an indexed document. */
export async function chat(
  documentId: string,
  question: string
): Promise<{ answer: string; sources: Source[] }> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: await authHeader(),
    body: JSON.stringify({ document_id: documentId, question }),
  });
  return handle(res);
}
