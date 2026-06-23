// Vercel serverless proxy → private Hugging Face Space.
// Browser calls same-origin /api/* with the Supabase JWT in Authorization.
// This function injects the HF gating token (Authorization) and forwards the
// Supabase JWT as X-Supabase-Auth, so both the HF router and our app authenticate.
// HF_TOKEN / HF_SPACE_URL are server-side env vars (no VITE_ prefix => never sent to the browser).
import type { VercelRequest, VercelResponse } from "@vercel/node";

export const config = { maxDuration: 60 };

const SPACE = process.env.HF_SPACE_URL;
const HF_TOKEN = process.env.HF_TOKEN;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!SPACE || !HF_TOKEN) {
    res.status(500).json({ detail: "Proxy missing HF_SPACE_URL or HF_TOKEN env." });
    return;
  }

  // Derive the subpath + query from req.url (robust; doesn't depend on the
  // catch-all param). e.g. "/api/chat?x=1" -> path "chat", search "?x=1".
  const parsed = new URL(req.url ?? "/", "http://localhost");
  const subPath = parsed.pathname.replace(/^\/api\/?/, "");
  const url = `${SPACE.replace(/\/$/, "")}/${subPath}${parsed.search}`;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${HF_TOKEN}`,
    "Content-Type": "application/json",
  };
  const supabaseAuth = req.headers["authorization"];
  if (supabaseAuth) headers["X-Supabase-Auth"] = String(supabaseAuth);

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = JSON.stringify(req.body ?? {});
  }

  try {
    const upstream = await fetch(url, init);
    const text = await upstream.text();
    const ct = upstream.headers.get("content-type");
    if (ct) res.setHeader("content-type", ct);
    res.status(upstream.status).send(text);
  } catch (e) {
    res.status(502).json({ detail: `Proxy error: ${e instanceof Error ? e.message : String(e)}` });
  }
}
