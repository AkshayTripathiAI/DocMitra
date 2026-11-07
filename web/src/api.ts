export type Status = "valid" | "expiring" | "expired" | "none";

export interface Field {
  key: string;
  label: string;
  value: string;
  sensitive: boolean;
  confidence?: number;
}

export interface DocumentOut {
  id: string;
  doc_type: string;
  doc_label: string;
  holder_name: string | null;
  expiry_date: string | null;
  status: Status;
  fields: Field[];
  notes: string[];
  filename: string;
  created_at: string;
}

export interface Reminder {
  id: string;
  title: string;
  due_date: string;
  done: boolean;
  overdue: boolean;
}

export interface DocType {
  code: string;
  label: string;
}

export interface NamePair {
  a: string;
  b: string;
  name_a: string;
  name_b: string;
  similarity: number;
  match: boolean;
}

// Empty in local dev (Vite proxies /api); set VITE_API_BASE to the backend URL in production.
const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () =>
    request<{ llm_configured: boolean; llm_model: string; demo_mode: boolean }>("/health"),
  docTypes: () => request<DocType[]>("/doc-types"),
  documents: () => request<DocumentOut[]>("/documents"),
  upload: (file: File, docType?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (docType) form.append("doc_type", docType);
    return request<DocumentOut>("/documents", { method: "POST", body: form });
  },
  remove: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  fileUrl: (id: string) => `${API_BASE}/api/documents/${id}/file`,
  nameCheck: () => request<{ documents: number; pairs: NamePair[] }>("/checks/names"),
  reminders: () => request<Reminder[]>("/reminders"),
  setReminderDone: (id: string, done: boolean) =>
    request<Reminder>(`/reminders/${id}`, json("PATCH", { done })),
  chat: (message: string, threadId: string) =>
    request<{ reply: string; tools_used: string[] }>(
      "/chat",
      json("POST", { message, thread_id: threadId }),
    ),
};
