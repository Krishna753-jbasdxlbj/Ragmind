import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../auth/AuthProvider";
import type { DocumentRow } from "../types";
import UploadPanel from "../components/UploadPanel";
import DocumentList from "../components/DocumentList";
import Chat from "../components/Chat";

export default function Workspace() {
  const { session, signOut } = useAuth();
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [selected, setSelected] = useState<DocumentRow | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadDocs = useCallback(async () => {
    const { data } = await supabase
      .from("documents")
      .select("*")
      .order("created_at", { ascending: false });
    if (data) {
      setDocs(data as DocumentRow[]);
      setSelected((cur) => (cur ? (data as DocumentRow[]).find((d) => d.id === cur.id) ?? cur : cur));
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

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" /> RAGmind
        </div>

        <UploadPanel onUploaded={loadDocs} />

        <DocumentList
          docs={docs}
          selectedId={selected?.id ?? null}
          onSelect={(d) => d.status === "ready" && setSelected(d)}
        />

        <div className="sidebar-foot">
          <span className="muted">{session?.user.email}</span>
          <button className="btn-ghost" onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>

      {selected && selected.status === "ready" ? (
        <Chat doc={selected} />
      ) : (
        <div className="main">
          <div className="messages">
            <div className="empty">
              <h3 style={{ marginBottom: 8 }}>Upload a document to begin</h3>
              <p>
                Drop a PDF in the sidebar. Once indexing finishes, select it to start a grounded
                conversation.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
