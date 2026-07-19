import { usePdfRag } from "./usePdfRag";
import { UploadScreen } from "./UploadScreen";
import { ProcessingScreen } from "./ProcessingScreen";
import { ChatScreen } from "./ChatScreen";
import { SideDrawer } from "./SideDrawer";

export function PdfRagApp() {
  const app = usePdfRag();

  let screen: React.ReactNode;
  if (app.state === "idle") {
    screen = <UploadScreen onFile={app.handleFile} error={app.uploadError} />;
  } else if (app.state === "processing") {
    screen = (
      <ProcessingScreen
        stages={app.stages}
        fileName={app.fileName}
        failed={app.failed}
        onRetry={app.reset}
      />
    );
  } else {
    screen = (
      <ChatScreen
        fileName={app.fileName}
        summary={app.summary}
        summaryOpen={app.summaryOpen}
        toggleSummary={app.toggleSummary}
        messages={app.messages}
        input={app.input}
        setInput={app.setInput}
        onSend={app.sendMessage}
        awaiting={app.awaitingReply}
      />
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => app.setMenuOpen(true)}
        aria-label="Open menu"
        className="fixed top-4 left-4 z-40 w-10 h-10 rounded-full hairline flex items-center justify-center bg-background/80 backdrop-blur hover:bg-[color:var(--surface-raised)] transition-colors"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-[color:var(--brass)]"
        >
          <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
        </svg>
      </button>
      {screen}
      <SideDrawer
        open={app.menuOpen}
        onClose={() => app.setMenuOpen(false)}
        history={[]}
        activeId={null}
        onSelect={() => {}}
        onNewChat={() => {
          app.setMenuOpen(false);
          app.reset();
        }}
      />
    </>
  );
}
