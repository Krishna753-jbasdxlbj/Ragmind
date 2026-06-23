import { useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabase";
import { chat } from "../api/rag";
import type { DocumentRow, MessageRow, Source } from "../types";

interface LocalMsg {
  role: "user" | "assistant";
  content: string;
  sources?: Source[] | null;
}

export default function Chat({ doc }: { doc: DocumentRow }) {
  const [messages, setMessages] = useState<LocalMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Load history when the selected document changes.
  useEffect(() => {
    setMessages([]);
    setError(null);
    supabase
      .from("messages")
      .select("*")
      .eq("document_id", doc.id)
      .order("created_at", { ascending: true })
      .then(({ data }) => {
        if (data) setMessages((data as MessageRow[]).map((m) => ({ role: m.role, content: m.content, sources: m.sources })));
      });
  }, [doc.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async () => {
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: q }]);
    setBusy(true);
    try {
      const { answer, sources } = await chat(doc.id, q);
      setMessages((m) => [...m, { role: "assistant", content: answer, sources }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="main">
      <div className="chat-head">
        <h2>{doc.filename}</h2>
        <span className="muted" style={{ fontSize: 13 }}>Answers are grounded in this document with page citations.</span>
      </div>

      <div className="messages">
        {messages.length === 0 && !busy && (
          <div className="empty">
            <h3 style={{ marginBottom: 8 }}>Ask anything</h3>
            <p>Questions are answered only from “{doc.filename}”. If it’s not in there, RAGmind says so.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.content}</div>
            {m.sources && m.sources.length > 0 && (
              <div className="sources">
                {m.sources.map((s, j) => (
                  <span key={j} className="chip">
                    {s.filename}{s.page ? `, p. ${s.page}` : ""}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="typing">RAGmind is reading the document…</div>}
        {error && <div className="error">{error}</div>}
        <div ref={endRef} />
      </div>

      <div className="composer">
        <textarea
          rows={1}
          placeholder="Ask a question about this document…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="btn-primary" onClick={send} disabled={busy || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
