export type DocStatus = "pending" | "indexing" | "ready" | "error";

export interface DocumentRow {
  id: string;
  user_id: string;
  filename: string;
  storage_path: string;
  status: DocStatus;
  error: string | null;
  created_at: string;
}

export interface Source {
  filename: string;
  page: number | null;
}

export interface MessageRow {
  id: string;
  document_id: string | null;
  role: "user" | "assistant";
  content: string;
  sources: Source[] | null;
  created_at: string;
}
