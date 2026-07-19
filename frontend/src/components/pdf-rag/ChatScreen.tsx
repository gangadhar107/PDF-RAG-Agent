import { useEffect, useRef } from "react";
import type { Message } from "./types";

interface ChatScreenProps {
  fileName: string | null;
  summary: string | null;
  summaryOpen: boolean;
  toggleSummary: () => void;
  messages: Message[];
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  awaiting: boolean;
}

export function ChatScreen({
  fileName,
  summary,
  summaryOpen,
  toggleSummary,
  messages,
  input,
  setInput,
  onSend,
  awaiting,
}: ChatScreenProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, awaiting]);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-[color:var(--hairline)] pl-20 pr-6 py-4">
        <div className="max-w-3xl mx-auto flex items-baseline justify-between gap-4">
          <div className="flex items-baseline gap-3 min-w-0">
            <div className="font-display text-xl text-foreground">
              PDF RAG Agent
            </div>
            {fileName ? (
              <div className="text-xs text-muted-foreground font-mono truncate">
                — {fileName}
              </div>
            ) : null}
          </div>
        </div>
      </header>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto" ref={scrollRef}>
        <div className="max-w-3xl mx-auto px-6 py-8">
          {/* Collapsible summary */}
          <section className="panel rounded-2xl mb-8 fade-up overflow-hidden">
            <button
              onClick={toggleSummary}
              className="w-full flex items-center justify-between px-6 py-4 text-left"
            >
              <span className="text-xs uppercase tracking-[0.3em] text-[color:var(--brass)]">
                Document Summary
              </span>
              <span className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                {summaryOpen ? "Collapse Summary" : "Expand Summary"}
              </span>
            </button>
            {summaryOpen ? (
              <div className="px-6 pb-6 border-t border-[color:var(--hairline)] pt-5">
                {summary ? (
                  <p className="text-[15px] leading-relaxed text-foreground font-light">
                    {summary}
                  </p>
                ) : (
                  <div className="space-y-2">
                    <div className="text-xs uppercase tracking-widest text-[color:var(--brass)] mb-3">
                      Summarizing…
                    </div>
                    <div className="h-3 shimmer rounded-full" />
                    <div className="h-3 shimmer rounded-full w-11/12" />
                    <div className="h-3 shimmer rounded-full w-9/12" />
                  </div>
                )}
              </div>
            ) : null}
          </section>

          {/* Messages */}
          <div className="space-y-6">
            {messages.length === 0 ? (
              <div className="text-center text-muted-foreground text-sm py-8 fade-up">
                Ask a question to begin.
              </div>
            ) : null}
            {messages.map((m) => (
              <MessageRow key={m.id} message={m} />
            ))}
          </div>
        </div>
      </div>

      {/* Sticky input bar */}
      <div className="sticky bottom-0 bg-background border-t border-[color:var(--hairline)]">
        <div className="max-w-3xl mx-auto px-6 py-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              onSend();
            }}
            className={`flex items-center gap-3 hairline rounded-full px-4 py-2.5 transition-opacity duration-300 ${
              awaiting
                ? "opacity-50"
                : "focus-within:border-[color:var(--brass)]"
            }`}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={awaiting}
              placeholder="Ask a question about this document..."
              className="flex-1 bg-transparent outline-none text-foreground placeholder:text-muted-foreground text-[15px] disabled:cursor-not-allowed px-2"
            />
            <button
              type="submit"
              disabled={awaiting || !input.trim()}
              className="px-4 py-1.5 rounded-full text-sm border border-[color:var(--brass)] text-[color:var(--brass)] hover:bg-[color:var(--brass)] hover:text-[color:var(--background)] transition-colors duration-300 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[color:var(--brass)]"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

/* ---- MessageRow (private to this screen) ---- */

function MessageRow({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end fade-up">
        <div className="max-w-[80%] px-4 py-3 bg-[color:var(--surface-raised)] hairline text-foreground text-[15px] leading-relaxed">
          {message.text}
        </div>
      </div>
    );
  }

  if (message.notFound) {
    return (
      <div className="flex justify-start fade-up">
        <div className="max-w-[85%] flex items-start gap-3 text-muted-foreground italic font-serif text-[15px] leading-relaxed py-2 border-l-2 border-[color:var(--hairline)] pl-4">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.25"
            className="mt-1 flex-shrink-0"
          >
            <circle cx="12" cy="12" r="9" />
            <path
              d="M9 10h.01M15 10h.01M9 16c1-1 2-1.5 3-1.5s2 .5 3 1.5"
              strokeLinecap="round"
            />
          </svg>
          <span>{message.text}</span>
        </div>
      </div>
    );
  }

  const showThinking = message.thinking && message.thinking.length > 0;

  return (
    <div className="flex justify-start fade-up">
      <div className="max-w-[85%] w-full">
        {showThinking ? (
          <details
            className="mb-5 text-[13px] border-l border-[color:var(--hairline)] pl-4 py-1"
            open={message.isStreaming ? true : undefined}
          >
            <summary className="cursor-pointer font-serif italic text-[color:var(--brass)] mb-2 outline-none select-none hover:text-foreground transition-colors">
              Thinking Process...
            </summary>
            <div className="font-sans whitespace-pre-wrap leading-relaxed font-light text-muted-foreground/70">
              {message.thinking}
            </div>
          </details>
        ) : null}

        {message.text ? (
          <p className="text-foreground text-[15px] leading-relaxed font-light">
            {message.text}
          </p>
        ) : message.isStreaming ? (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--brass)] pulse-brass" />
            <span className="italic font-serif">Writing answer…</span>
          </div>
        ) : null}

        {message.sources && message.sources.length > 0 ? (
          <div className="mt-4 pt-3 border-t border-[color:var(--hairline)]">
            <div className="text-[10px] uppercase tracking-[0.3em] text-[color:var(--brass)] mb-2">
              Sources
            </div>
            <ul className="space-y-1">
              {message.sources.map((s, i) => (
                <li key={i} className="text-xs text-muted-foreground">
                  <span className="text-foreground">{s.section}</span>{" "}
                  <span className="text-[color:var(--brass-dim)]">
                    (Page {s.page})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
