import { useState } from "react";
import type { DocStatus, DocumentRow } from "../types";

const STATUS_LABEL: Record<DocStatus, string> = {
  pending: "indexing",
  indexing: "indexing",
  ready: "ready",
  error: "failed",
};

export default function DocumentList({
  docs,
  selectedId,
  busyId,
  onSelect,
  onDelete,
}: {
  docs: DocumentRow[];
  selectedId: string | null;
  /** Id of a document currently being deleted (row shows a spinner / is disabled). */
  busyId: string | null;
  onSelect: (d: DocumentRow) => void;
  onDelete: (d: DocumentRow) => void;
}) {
  if (docs.length === 0) {
    return <p className="muted doc-empty">No documents yet — upload a PDF to get started.</p>;
  }
  return (
    <div className="doc-list">
      {docs.map((d) => {
        const deleting = d.id === busyId;
        return (
          <div
            key={d.id}
            className={`doc-item${d.id === selectedId ? " active" : ""}${
              d.status === "error" ? " is-error" : ""
            }`}
            role="button"
            tabIndex={0}
            aria-current={d.id === selectedId}
            onClick={() => !deleting && onSelect(d)}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !deleting) {
                e.preventDefault();
                onSelect(d);
              }
            }}
          >
            <span className={`status-dot ${d.status}`} aria-hidden />
            <span className="doc-meta">
              <span className="doc-name" title={d.filename}>
                {d.filename}
              </span>
              <span className={`status ${d.status}`}>
                {STATUS_LABEL[d.status]}
                {(d.status === "indexing" || d.status === "pending") && (
                  <span className="status-spinner" aria-hidden />
                )}
              </span>
            </span>
            <DeleteButton deleting={deleting} onConfirm={() => onDelete(d)} />
          </div>
        );
      })}
    </div>
  );
}

function DeleteButton({
  deleting,
  onConfirm,
}: {
  deleting: boolean;
  onConfirm: () => void;
}) {
  const [confirm, setConfirm] = useState(false);

  if (deleting) {
    return <span className="doc-del-spinner" aria-label="Deleting" />;
  }

  return (
    <button
      type="button"
      className={`doc-del${confirm ? " confirm" : ""}`}
      title={confirm ? "Click again to delete" : "Delete document"}
      aria-label={confirm ? "Confirm delete" : "Delete document"}
      onClick={(e) => {
        e.stopPropagation();
        if (confirm) {
          onConfirm();
          setConfirm(false);
        } else {
          setConfirm(true);
          // Auto-cancel the armed state if the user doesn't follow through.
          window.setTimeout(() => setConfirm(false), 2600);
        }
      }}
      onMouseLeave={() => setConfirm(false)}
    >
      {confirm ? "Delete?" : <TrashIcon />}
    </button>
  );
}

function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  );
}
