import type { DocumentRow } from "../types";

export default function DocumentList({
  docs,
  selectedId,
  onSelect,
}: {
  docs: DocumentRow[];
  selectedId: string | null;
  onSelect: (d: DocumentRow) => void;
}) {
  if (docs.length === 0) {
    return <p className="muted" style={{ fontSize: 13 }}>No documents yet.</p>;
  }
  return (
    <div className="doc-list">
      {docs.map((d) => (
        <button
          key={d.id}
          className={`doc-item${d.id === selectedId ? " active" : ""}`}
          onClick={() => onSelect(d)}
          disabled={d.status === "error"}
        >
          <span className="doc-name">{d.filename}</span>
          <span className={`status ${d.status}`}>
            {d.status === "indexing" || d.status === "pending" ? "indexing…" : d.status}
          </span>
        </button>
      ))}
    </div>
  );
}
