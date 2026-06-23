import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
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
  // A question typed before the document finished indexing. It is answered
  // automatically once the doc flips to "ready".
  const [queued, setQueued] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const ready = doc.status === "ready";
  const indexing = doc.status === "pending" || doc.status === "indexing";

  // Load history when the selected document changes; clear any in-flight queue.
  useEffect(() => {
    setMessages([]);
    setError(null);
    setQueued(null);
    supabase
      .from("messages")
      .select("*")
      .eq("document_id", doc.id)
      .order("created_at", { ascending: true })
      .then(({ data }) => {
        if (data)
          setMessages(
            (data as MessageRow[]).map((m) => ({
              role: m.role,
              content: m.content,
              sources: m.sources,
            }))
          );
      });
  }, [doc.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, queued]);

  const runChat = async (q: string) => {
    setBusy(true);
    setError(null);
    try {
      const { answer, sources } = await chat(doc.id, q);
      setMessages((m) => [...m, { role: "assistant", content: answer, sources }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  };

  // Fire the queued question as soon as the document becomes ready.
  useEffect(() => {
    if (ready && queued && !busy) {
      const q = queued;
      setQueued(null);
      void runChat(q);
    }
    // If indexing failed while a question was waiting, surface it.
    if (doc.status === "error" && queued) {
      setQueued(null);
      setError("Indexing failed for this document, so your question couldn't be answered.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc.status, queued, busy]);

  const send = () => {
    const q = input.trim();
    if (!q || busy || queued) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    if (ready) {
      void runChat(q);
    } else {
      // Document still indexing — hold the question and answer it later.
      setQueued(q);
    }
  };

  const onInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const ta = taRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
    }
  };

  return (
    <div className="main">
      <div className="chat-head">
        <div className="chat-head-row">
          <h2 title={doc.filename}>{doc.filename}</h2>
          <span className={`doc-pill ${doc.status}`}>
            <span className={`status-dot ${doc.status}`} aria-hidden />
            {ready ? "Ready" : indexing ? "Indexing…" : "Error"}
          </span>
        </div>
        <span className="muted chat-sub">
          Answers are grounded in this document, with page citations.
        </span>
      </div>

      {indexing && (
        <div className="index-banner">
          <span className="status-spinner dark" aria-hidden />
          Indexing this PDF… you can type your question now and it’ll be answered
          automatically when it’s ready.
        </div>
      )}

      <div className="messages">
        {messages.length === 0 && !busy && !queued && (
          <div className="empty">
            <div className="empty-mark" aria-hidden>
              <span className="dot" />
            </div>
            <h3>Ask anything</h3>
            <p>
              Questions are answered only from “{doc.filename}”. If the answer isn’t in
              there, RAGmind tells you so.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="msg-avatar" aria-hidden>
              {m.role === "user" ? "You" : <span className="dot" />}
            </div>
            <div className="msg-body">
              <div className="bubble">{m.content}</div>
              {m.sources && m.sources.length > 0 && (
                <div className="sources">
                  {m.sources.map((s, j) => (
                    <span key={j} className="chip">
                      {s.filename}
                      {s.page ? `, p. ${s.page}` : ""}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {queued && (
          <div className="typing">
            <span className="status-spinner dark" aria-hidden /> Waiting for indexing to
            finish, then I’ll answer…
          </div>
        )}
        {busy && (
          <div className="typing">
            <span className="status-spinner dark" aria-hidden /> RAGmind is reading the
            document…
          </div>
        )}
        {error && <div className="error">{error}</div>}
        <div ref={endRef} />
      </div>

      <div className="composer">
        <textarea
          ref={taRef}
          rows={1}
          placeholder={
            ready
              ? "Ask a question about this document…"
              : "Type your question — it’ll be answered once indexing finishes…"
          }
          value={input}
          onChange={onInput}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button
          className="btn-primary send-btn"
          onClick={send}
          disabled={!input.trim() || busy || !!queued}
          aria-label="Send"
        >
          <SendIcon />
        </button>
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}
