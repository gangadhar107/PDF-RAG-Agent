import { useRef, useState } from "react";

interface UploadScreenProps {
  onFile: (f: File | null) => void;
  error: string | null;
}

export function UploadScreen({ onFile, error }: UploadScreenProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-2xl fade-up">
        <div className="text-center mb-14">
          <div className="text-xs uppercase tracking-[0.35em] text-[color:var(--brass)] mb-5">
            Document Intelligence
          </div>
          <h1 className="font-display text-5xl md:text-6xl text-foreground mb-4">
            PDF RAG Agent
          </h1>
          <p className="text-muted-foreground text-lg font-light">
            Upload a PDF to begin chatting
          </p>
        </div>

        <label
          htmlFor="pdf-input"
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            onFile(e.dataTransfer.files?.[0] ?? null);
          }}
          className={`block cursor-pointer panel rounded-2xl px-8 py-10 text-center transition-all duration-[350ms] ease-out ${
            dragOver
              ? "border-[color:var(--brass)] bg-[color:var(--surface-raised)]"
              : ""
          }`}
          style={{ borderStyle: "dashed" }}
        >
          <div className="mx-auto mb-6 w-14 h-14 flex items-center justify-center">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.25"
              className="text-[color:var(--brass)]"
            >
              <path
                d="M12 3v13m0 0l-5-5m5 5l5-5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div className="font-display text-xl text-foreground mb-2">
            Drag &amp; Drop PDF Here
          </div>
          <div className="text-sm text-muted-foreground">or click to upload</div>
          <input
            id="pdf-input"
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
        </label>

        {error ? (
          <div
            role="alert"
            className="mt-5 fade-up text-sm text-[color:var(--danger)] flex items-start gap-2"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="mt-0.5 flex-shrink-0"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
            </svg>
            <span>{error}</span>
          </div>
        ) : null}
      </div>
    </main>
  );
}
