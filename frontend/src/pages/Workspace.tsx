import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../auth/AuthProvider";
import { deleteDocument } from "../api/rag";
import type { DocumentRow } from "../types";
import UploadPanel from "../components/UploadPanel";
import DocumentList from "../components/DocumentList";
import Chat from "../components/Chat";

export default function Workspace() {
  const { session, signOut } = useAuth();
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [selected, setSelected] = useState<DocumentRow | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadDocs = useCallback(async () => {
    const { data } = await supabase
      .from("documents")
      .select("*")
      .order("created_at", { ascending: false });
    if (data) {
      const rows = data as DocumentRow[];
      setDocs(rows);
      // Keep the selected document's status fresh (e.g. indexing -> ready).
      setSelected((cur) => (cur ? rows.find((d) => d.id === cur.id) ?? null : cur));
    }
  }, []);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  // Poll while anything is still indexing.
  useEffect(() => {
    const pending = docs.some((d) => d.status === "pending" || d.status === "indexing");
    if (pending && pollRef.current === null) {
      pollRef.current = window.setInterval(loadDocs, 3000);
    } else if (!pending && pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [docs, loadDocs]);

  // Allow selecting any document that isn't in an error state — Chat handles the
  // "still indexing" case by queueing the question until the doc is ready.
  const handleSelect = (d: DocumentRow) => {
    if (d.status === "error") return;
    setError(null);
    setSelected(d);
  };

  const handleDelete = async (d: DocumentRow) => {
    setError(null);
    setDeletingId(d.id);
    // Optimistic: drop it from the list immediately.
    setDocs((cur) => cur.filter((x) => x.id !== d.id));
    if (selected?.id === d.id) setSelected(null);
    try {
      await deleteDocument(d.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
      await loadDocs(); // Re-sync on failure so the row reappears.
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" /> RAGmind
        </div>

        <UploadPanel onUploaded={loadDocs} />

        <div className="doc-section">
          <span className="doc-section-label">Documents</span>
          <DocumentList
            docs={docs}
            selectedId={selected?.id ?? null}
            busyId={deletingId}
            onSelect={handleSelect}
            onDelete={handleDelete}
          />
          {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
        </div>

        <div className="sidebar-foot">
          <span className="muted user-email" title={session?.user.email}>
            {session?.user.email}
          </span>
          <button className="btn-ghost" onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>

      {selected ? (
        <Chat doc={selected} />
      ) : (
        <div className="main">
          <div className="messages">
            <div className="empty">
              <div className="empty-mark" aria-hidden>
                <span className="dot" />
              </div>
              <h3>Upload a document to begin</h3>
              <p>
                Drop a PDF in the sidebar. You can start typing your question right away —
                RAGmind answers the moment indexing finishes.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
