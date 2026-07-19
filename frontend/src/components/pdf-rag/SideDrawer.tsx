export interface ChatHistoryItem {
  id: string;
  title: string;
  timestamp: string;
}

interface SideDrawerProps {
  open: boolean;
  onClose: () => void;
  history: ChatHistoryItem[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}

export function SideDrawer({
  open,
  onClose,
  history,
  activeId,
  onSelect,
  onNewChat,
}: SideDrawerProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-300 ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />

      {/* Drawer */}
      <aside
        className={`fixed top-0 left-0 z-50 h-full w-[320px] bg-[color:var(--surface)] border-r border-[color:var(--hairline)] rounded-r-2xl shadow-2xl flex flex-col transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[color:var(--hairline)]">
          <div className="text-xs uppercase tracking-[0.3em] text-[color:var(--brass)]">
            Conversations
          </div>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-[color:var(--surface-raised)] transition-colors text-muted-foreground"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* New Chat */}
        <div className="px-4 pt-4">
          <button
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl hairline text-sm text-foreground hover:bg-[color:var(--surface-raised)] transition-colors"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-[color:var(--brass)]"
            >
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
            <span>New Chat</span>
          </button>
        </div>

        {/* Conversation list */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {history.length === 0 ? (
            <div className="text-center text-muted-foreground text-xs py-8">
              No conversations yet
            </div>
          ) : (
            history.map((c) => {
              const active = c.id === activeId;
              return (
                <button
                  key={c.id}
                  onClick={() => onSelect(c.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-xl transition-colors duration-200 ${
                    active
                      ? "bg-[color:var(--surface-raised)] border border-[color:var(--brass)]/40"
                      : "hover:bg-[color:var(--surface-raised)] border border-transparent"
                  }`}
                >
                  <div className="text-sm text-foreground truncate">
                    {c.title}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    {c.timestamp}
                  </div>
                </button>
              );
            })
          )}
        </nav>

        {/* TODO: User profile — uncomment when auth is implemented
        <div className="border-t border-[color:var(--hairline)] px-4 py-4">
          <div className="flex items-center gap-3 p-2 rounded-xl hover:bg-[color:var(--surface-raised)] transition-colors cursor-pointer">
            <div className="w-10 h-10 rounded-full bg-[color:var(--brass)]/15 border border-[color:var(--brass)]/40 flex items-center justify-center text-[color:var(--brass)] text-sm font-medium">
              AM
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm text-foreground truncate">Alex Morgan</div>
              <div className="text-[11px] text-muted-foreground truncate">
                alex.morgan@example.com
              </div>
            </div>
            <span className="text-[10px] uppercase tracking-widest text-[color:var(--brass)] px-2 py-1 rounded-full border border-[color:var(--brass)]/40">
              Pro
            </span>
          </div>
        </div>
        */}
      </aside>
    </>
  );
}
