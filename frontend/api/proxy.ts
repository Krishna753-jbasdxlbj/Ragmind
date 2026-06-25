// Vercel serverless proxy → private Hugging Face Space.
// vercel.json rewrites /api/:path* -> /api/proxy?path=:path*, so this single
// function handles every /api/* request (nested paths included). The bracket
// catch-all ([...path].ts) did NOT match multi-segment paths in this Vite
// project, which 404'd /api/document/{id}.
//
// Browser calls same-origin /api/* with the Supabase JWT in Authorization.
// This injects the HF gating token (Authorization) and forwards the Supabase
// JWT as X-Supabase-Auth, so both the HF router and our app authenticate.
// HF_TOKEN / HF_SPACE_URL are server-side env (no VITE_ prefix => never in the browser).
import type { VercelRequest, VercelResponse } from "@vercel/node";

export const config = { maxDuration: 60 };

const SPACE = process.env.HF_SPACE_URL;
const HF_TOKEN = process.env.HF_TOKEN;

function subPathOf(req: VercelRequest): string {
  const q = req.query.path;
  if (q) return Array.isArray(q) ? q.join("/") : q;
  // Fallback: derive from the URL if the rewrite param is absent.
  const parsed = new URL(req.url ?? "/", "http://localhost");
  return parsed.pathname.replace(/^\/api\/?/, "").replace(/^proxy\/?/, "");
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!SPACE || !HF_TOKEN) {
    res.status(500).json({ detail: "Proxy missing HF_SPACE_URL or HF_TOKEN env." });
    return;
  }

  const path = subPathOf(req);
  const url = `${SPACE.replace(/\/$/, "")}/${path}`;

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
