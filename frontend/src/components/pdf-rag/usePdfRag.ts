import { useCallback, useRef, useState } from "react";
import {
  askQuestionStream,
  fetchSummary,
  subscribeEvents,
  uploadPdf,
  type StageEventData,
} from "./api";
import {
  type AppState,
  type Message,
  type Stage,
  type StageKey,
  INITIAL_STAGES,
  uid,
} from "./types";

export function usePdfRag() {
  const [state, setState] = useState<AppState>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [stages, setStages] = useState<Stage[]>(INITIAL_STAGES);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [awaitingReply, setAwaitingReply] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const cleanupRef = useRef<(() => void) | null>(null);

  // Subscribe to SSE stage events and drive the stage UI.
  const runProcessing = useCallback((newDocId: string) => {
    setStages(INITIAL_STAGES.map((s) => ({ ...s })));
    setSummary(null);

    const setStage = (key: StageKey, patch: Partial<Stage>) => {
      setStages((prev) =>
        prev.map((s) => (s.key === key ? { ...s, ...patch } : s)),
      );
    };

    let transitioned = false;

    const unsubscribe = subscribeEvents(newDocId, (e: StageEventData) => {
      const key = e.stage as StageKey;
      setStage(key, {
        status: e.status,
        progress: e.progress ?? undefined,
        error: e.message ?? undefined,
      });

      // Ready fires on embed+index (Option B) → move to chat 500ms later.
      if (key === "ready" && e.status === "completed" && !transitioned) {
        transitioned = true;
        window.setTimeout(() => setState("chat"), 500);
      }
      // Summary lands independently → fetch and show it.
      if (key === "summarizing" && e.status === "completed") {
        fetchSummary(newDocId)
          .then((r) => setSummary(r.summary))
          .catch(() => {});
      }
    });

    return unsubscribe;
  }, []);

  const handleFile = async (file: File | null) => {
    if (!file) return;
    setUploadError(null);

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setUploadError(
        "That doesn't look like a PDF. Please upload a .pdf file.",
      );
      return;
    }
    if (file.size < 100) {
      setUploadError("This PDF appears to be empty or corrupted.");
      return;
    }

    setFileName(file.name);
    setMessages([]);
    setState("processing");
    cleanupRef.current?.();

    try {
      const { doc_id } = await uploadPdf(file);
      setDocId(doc_id);
      cleanupRef.current = runProcessing(doc_id) ?? null;
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : "Upload failed.",
      );
      setState("idle");
    }
  };

  const reset = () => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState("idle");
    setFileName(null);
    setDocId(null);
    setUploadError(null);
    setStages(INITIAL_STAGES);
    setSummary(null);
    setMessages([]);
    setInput("");
    setAwaitingReply(false);
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || awaitingReply || !docId) return;

    const userMsg: Message = { id: uid(), role: "user", text };
    // history = prior turns (before this one) for §4.0 query rewriting
    const history = messages.map((m) => ({ role: m.role, content: m.text }));
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setAwaitingReply(true);

    const assistantMsgId = uid();
    const draftMsg: Message = {
      id: assistantMsgId,
      role: "assistant",
      text: "",
      thinking: "",
      isStreaming: true,
    };
    setMessages((m) => [...m, draftMsg]);

    let accumulatedText = "";

    try {
      await askQuestionStream(
        docId,
        text,
        history,
        (event) => {
          if (event.type === "token" && event.text) {
            accumulatedText += event.text;

            const step3Index = accumulatedText.indexOf("STEP 3");
            let thinking = accumulatedText;
            let answerText = "";

            if (step3Index !== -1) {
              thinking = accumulatedText.substring(0, step3Index).trim();
              let answerPart = accumulatedText.substring(
                step3Index + "STEP 3".length,
              );

              const colonIdx = answerPart.indexOf(":");
              if (colonIdx !== -1 && colonIdx < 15) {
                answerPart = answerPart.substring(colonIdx + 1);
              }
              answerText = answerPart.trim();
            }

            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? { ...msg, thinking, text: answerText }
                  : msg,
              ),
            );
          } else if (event.type === "done") {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      text: event.text ?? "",
                      notFound: event.notFound ?? false,
                      isStreaming: false,
                      sources: event.notFound
                        ? undefined
                        : event.sources
                            ?.filter((s) => s.section || s.page != null)
                            .map((s) => ({
                              section: s.section ?? "",
                              page: s.page ?? 0,
                            })),
                    }
                  : msg,
              ),
            );
          }
        },
        () => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    text: "Something went wrong answering that. Please try again.",
                    notFound: true,
                    isStreaming: false,
                  }
                : msg,
            ),
          );
        },
      );
    } catch {
      // handled via onError callback
    } finally {
      setAwaitingReply(false);
    }
  };

  const failedStage = stages.find((s) => s.status === "failed");

  return {
    state,
    fileName,
    uploadError,
    stages,
    summary,
    summaryOpen,
    messages,
    input,
    awaitingReply,
    menuOpen,
    failed: !!failedStage,
    setInput,
    setMenuOpen,
    toggleSummary: () => setSummaryOpen((v) => !v),
    handleFile,
    reset,
    sendMessage,
  };
}
