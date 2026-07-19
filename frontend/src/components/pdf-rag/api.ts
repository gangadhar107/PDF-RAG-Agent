// API client for the FastAPI backend (topology A: separate origin, CORS).
// Base URL is configurable via VITE_API_URL; defaults to localhost:8000.

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface UploadResponse {
  doc_id: string;
  filename: string;
}

export interface StageEventData {
  stage: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number | null;
  message: string | null;
  doc_id: string;
}

export interface QuerySource {
  section: string | null;
  page: number | null;
}

export interface QueryResponse {
  text: string;
  sources: QuerySource[];
  notFound: boolean;
  rewritten: string | null;
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Upload failed");
  return res.json();
}

// Subscribe to the SSE pipeline-progress stream. Returns an unsubscribe fn.
export function subscribeEvents(
  docId: string,
  onEvent: (e: StageEventData) => void,
  onError?: () => void,
): () => void {
  const es = new EventSource(`${API}/events/${docId}`);
  es.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as StageEventData);
    } catch {
      /* ignore malformed */
    }
  };
  es.onerror = () => {
    es.close();
    onError?.();
  };
  return () => es.close();
}

export async function askQuestion(
  docId: string,
  question: string,
  history: { role: string; content: string }[],
): Promise<QueryResponse> {
  const res = await fetch(`${API}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_id: docId, question, history }),
  });
  if (!res.ok) throw new Error("Query failed");
  return res.json();
}

export async function askQuestionStream(
  docId: string,
  question: string,
  history: { role: string; content: string }[],
  onEvent: (event: {
    type: string;
    text?: string;
    sources?: QuerySource[];
    notFound?: boolean;
  }) => void,
  onError?: (err: any) => void,
): Promise<void> {
  try {
    const res = await fetch(`${API}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, question, history }),
    });
    if (!res.ok) throw new Error("Query stream failed");
    if (!res.body) throw new Error("ReadableStream not supported");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.trim()) continue;
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.substring(6));
            onEvent(data);
          } catch {
            // ignore malformed
          }
        }
      }
    }
  } catch (err) {
    onError?.(err);
    throw err;
  }
}


export async function fetchSummary(
  docId: string,
): Promise<{ summary: string | null; summary_status: string }> {
  const res = await fetch(`${API}/summary/${docId}`);
  if (!res.ok) throw new Error("Summary fetch failed");
  return res.json();
}
