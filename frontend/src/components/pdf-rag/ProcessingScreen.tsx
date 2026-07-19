import type { Stage } from "./types";

interface ProcessingScreenProps {
  stages: Stage[];
  fileName: string | null;
  failed: boolean;
  onRetry: () => void;
}

export function ProcessingScreen({
  stages,
  fileName,
  failed,
  onRetry,
}: ProcessingScreenProps) {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-xl fade-up">
        <div className="mb-10">
          <div className="text-xs uppercase tracking-[0.35em] text-[color:var(--brass)] mb-3">
            Processing
          </div>
          <h2 className="font-display text-3xl text-foreground mb-1">
            Preparing your document
          </h2>
          {fileName ? (
            <p className="text-sm text-muted-foreground font-mono truncate">
              {fileName}
            </p>
          ) : null}
        </div>

        <ol className="panel px-8 py-7 space-y-1">
          {stages.map((s) => (
            <StageRow key={s.key} stage={s} />
          ))}
        </ol>

        {failed ? (
          <div className="mt-6 fade-up flex justify-center">
            <button
              onClick={onRetry}
              className="px-6 py-2.5 text-sm tracking-wide hairline hover:bg-[color:var(--surface-raised)] transition-colors duration-300 text-foreground"
            >
              Retry Upload
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}

/* ---- StageRow (private to this screen) ---- */

function StageRow({ stage }: { stage: Stage }) {
  const color =
    stage.status === "completed"
      ? "var(--success)"
      : stage.status === "running"
        ? "var(--brass)"
        : stage.status === "failed"
          ? "var(--danger)"
          : "var(--muted-foreground)";

  return (
    <li className="flex items-center gap-4 py-3 border-b last:border-b-0 border-[color:var(--hairline)]">
      <span
        className={`inline-flex w-2.5 h-2.5 rounded-full ${
          stage.status === "running" ? "pulse-brass" : ""
        }`}
        style={{ backgroundColor: color }}
      />
      <span
        className={`flex-1 text-sm ${
          stage.status === "pending"
            ? "text-muted-foreground"
            : stage.status === "failed"
              ? "text-[color:var(--danger)]"
              : "text-foreground"
        }`}
      >
        {stage.label}
        {stage.status === "running" && typeof stage.progress === "number" ? (
          <span className="text-muted-foreground"> ({stage.progress}%)</span>
        ) : null}
        {stage.status === "failed" && stage.error ? (
          <span className="text-[color:var(--danger)]"> — {stage.error}</span>
        ) : null}
      </span>
      {stage.status === "completed" ? (
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-[color:var(--success)]"
        >
          <path
            d="M4 12l5 5L20 6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : null}
    </li>
  );
}
