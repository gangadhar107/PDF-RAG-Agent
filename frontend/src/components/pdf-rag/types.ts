export type AppState = "idle" | "processing" | "chat";
export type StageStatus = "pending" | "running" | "completed" | "failed";
export type StageKey =
  | "validating"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexing"
  | "ready"
  | "summarizing";

export interface Stage {
  key: StageKey;
  label: string;
  status: StageStatus;
  progress?: number;
  error?: string;
}

export interface Source {
  section: string;
  page: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  thinking?: string;
  sources?: Source[];
  notFound?: boolean;
  isStreaming?: boolean;
}

export const INITIAL_STAGES: Stage[] = [
  { key: "validating", label: "Validating", status: "pending" },
  { key: "extracting", label: "Extracting", status: "pending" },
  { key: "chunking", label: "Chunking", status: "pending" },
  { key: "embedding", label: "Embedding", status: "pending" },
  { key: "indexing", label: "Indexing", status: "pending" },
  { key: "ready", label: "Ready", status: "pending" },
  { key: "summarizing", label: "Summarizing", status: "pending" },
];

export function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}
