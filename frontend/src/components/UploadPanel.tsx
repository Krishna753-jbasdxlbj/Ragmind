import { useRef, useState } from "react";
import { supabase, DOCUMENTS_BUCKET } from "../lib/supabase";
import { indexDocument } from "../api/rag";
import { useAuth } from "../auth/AuthProvider";

export default function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const { session } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are supported.");
      return;
    }
    const userId = session!.user.id;
    setBusy(true);
    try {
      // Path must start with the user's id (matches storage RLS).
      const path = `${userId}/${crypto.randomUUID()}-${file.name}`;
      const up = await supabase.storage.from(DOCUMENTS_BUCKET).upload(path, file);
      if (up.error) throw up.error;

      const ins = await supabase
        .from("documents")
        .insert({ user_id: userId, filename: file.name, storage_path: path, status: "pending" })
        .select()
        .single();
      if (ins.error) throw ins.error;

      await indexDocument(ins.data.id);
      onUploaded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div
        className={`uploader${drag ? " drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
      >
        {busy ? "Uploading…" : "Drop a PDF here, or click to browse"}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
      </div>
      {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}
