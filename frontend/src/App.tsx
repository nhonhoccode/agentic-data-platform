import { useCallback, useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useConversations } from "@/hooks/useConversations";
import { ChatMessage } from "@/components/ChatMessage";
import { Composer } from "@/components/Composer";
import { Sparkles, Trash2, Zap, LogOut, UserCircle2, Download, Crown, ShieldCheck } from "lucide-react";
import { exportConversation } from "@/lib/api";
import { AdminPanel } from "@/components/AdminPanel";
import { SuggestedQuestions } from "@/components/SuggestedQuestions";
import { Landing } from "@/components/Landing";
import { Login } from "@/components/Login";
import { Sidebar, SidebarToggle, useSidebarCollapsed } from "@/components/Sidebar";
import {
  clearStoredSession,
  getStoredSession,
  hasFeature,
  setStoredSession,
  verifyMe,
  type StoredSession,
} from "@/lib/session";

type Screen = "landing" | "login" | "chat";

export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [session, setSession] = useState<StoredSession | null>(null);
  const [bootChecked, setBootChecked] = useState(false);

  // On first mount, try to restore the session by validating the stored token.
  useEffect(() => {
    let cancelled = false;
    const stored = getStoredSession();
    if (!stored) {
      setBootChecked(true);
      return;
    }
    (async () => {
      const me = await verifyMe();
      if (cancelled) return;
      if (me) {
        const next: StoredSession = {
          token: stored.token,
          username: me.username,
          tier: me.tier,
          is_admin: me.is_admin,
          features: me.features,
        };
        setStoredSession(next);
        setSession(next);
        setScreen("chat");
      } else {
        clearStoredSession();
      }
      setBootChecked(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!bootChecked) {
    return (
      <div className="flex h-screen items-center justify-center bg-yellow-100">
        <div className="rounded-md border-2 border-black bg-white px-6 py-3 text-sm font-bold uppercase neo-shadow-sm">
          Đang kiểm tra session…
        </div>
      </div>
    );
  }

  if (screen === "landing") {
    return <Landing onEnter={() => setScreen("login")} />;
  }

  if (screen === "login") {
    return (
      <Login
        onBack={() => setScreen("landing")}
        onSuccess={(s) => {
          setSession(s);
          setScreen("chat");
        }}
      />
    );
  }

  return (
    <ChatScreen
      session={session ?? { token: "", username: "user", tier: "basic", is_admin: false, features: [] }}
      onLogout={() => {
        clearStoredSession();
        setSession(null);
        setScreen("landing");
      }}
    />
  );
}

function ChatScreen({
  session,
  onLogout,
}: {
  session: StoredSession;
  onLogout: () => void;
}) {
  const username = session.username;
  const webSearchAllowed = hasFeature(session, "web_search");
  const exportAllowed = hasFeature(session, "export");
  const tier = session.tier ?? "basic";
  const isAdmin = !!session.is_admin || tier === "admin";
  const [adminOpen, setAdminOpen] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [desktopCollapsed, toggleDesktopCollapsed] = useSidebarCollapsed();

  const {
    conversations,
    loading: conversationsLoading,
    refetch: refetchConversations,
    create: createConv,
    remove: removeConv,
    rename: renameConv,
    upsertLocal,
  } = useConversations();

  const onConversationCreated = useCallback(
    (id: string, title: string) => {
      // Backend auto-created (or resolved) a conversation during stream.
      // Update local id immediately so subsequent sends reuse it.
      setActiveConversationId(id);
      upsertLocal({ id, title });
      // Refresh once the stream settles so message_count + updated_at align.
      window.setTimeout(() => {
        void refetchConversations();
      }, 800);
    },
    [refetchConversations, upsertLocal],
  );

  const { messages, busy, loadingConversation, sendMessage, stop, clear } = useChat({
    activeConversationId,
    webSearchEnabled,
    onConversationCreated,
  });

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleNewChat = useCallback(async () => {
    // Don't actually call POST — just clear active id, the next send will
    // auto-create via the SSE `conversation` event. Saves a round-trip.
    setActiveConversationId(null);
    clear();
    setSidebarOpen(false);
  }, [clear]);

  const handleSelectConversation = useCallback((id: string | null) => {
    setActiveConversationId(id);
    setSidebarOpen(false);
  }, []);

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      await removeConv(id);
      if (id === activeConversationId) {
        setActiveConversationId(null);
        clear();
      }
    },
    [removeConv, activeConversationId, clear],
  );

  const lastAssistantMessage = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && !m.streaming);
  const lastIntent = lastAssistantMessage?.intent ?? null;
  const activeMeta = conversations.find((c) => c.id === activeConversationId);

  // CTA #1: "Vẫn tra cứu Internet" on out-of-domain blocks → resend with
  // force_web_search=true so the domain filter is bypassed.
  const handleRetryWithForceSearch = useCallback(
    (query: string) => {
      void sendMessage(query, { webSearchEnabled: true, forceWebSearch: true });
    },
    [sendMessage],
  );

  // CTA #2: "Bật & hỏi lại" on toggle-off blocks → turn on the global toggle
  // and resend the same query (no force, just standard web search).
  const handleTurnOnToggle = useCallback(
    (query: string) => {
      setWebSearchEnabled(true);
      void sendMessage(query, { webSearchEnabled: true });
    },
    [sendMessage],
  );

  const handleExport = useCallback(async () => {
    if (!activeConversationId) return;
    try {
      const bundle = await exportConversation(activeConversationId);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safe = (activeMeta?.title || "conversation").replace(/[^a-zA-Z0-9-_]/g, "_");
      a.href = url;
      a.download = `olist-${safe}-${activeConversationId.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (exc) {
      console.warn("export failed", exc);
    }
  }, [activeConversationId, activeMeta]);

  // Unused but kept for future "rename current chat" UI.
  void createConv;

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        conversations={conversations}
        activeId={activeConversationId}
        loading={conversationsLoading}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        onRename={renameConv}
        mobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        desktopCollapsed={desktopCollapsed}
        onToggleDesktopCollapsed={toggleDesktopCollapsed}
      />

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b-2 border-black bg-yellow-300 px-4 py-3 md:px-6">
          <div className="flex items-center gap-3">
            <SidebarToggle onClick={() => setSidebarOpen(true)} />
            <div className="flex h-10 w-10 items-center justify-center rounded-md border-2 border-black bg-pink-400 neo-shadow-sm">
              <Sparkles className="h-5 w-5 text-black" strokeWidth={3} />
            </div>
            <div className="flex min-w-0 flex-col">
              <h1 className="text-base font-black uppercase tracking-tight truncate">
                {activeMeta?.title || "New chat"}
              </h1>
              <span className="inline-flex w-fit items-center gap-1 rounded-md border border-black bg-lime-300 px-1.5 py-0.5 text-[10px] font-bold uppercase">
                <Zap className="h-2.5 w-2.5" strokeWidth={3} />
                multi-agent · RAG
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-2.5 py-1.5 text-xs font-bold uppercase neo-shadow-sm">
              <UserCircle2 className="h-4 w-4" strokeWidth={3} />
              {username}
            </span>
            {isAdmin && (
              <button
                onClick={() => setAdminOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-yellow-200 px-3 py-1.5 text-xs font-black uppercase neo-shadow-sm neo-press"
                title="Quản lý user"
              >
                <ShieldCheck className="h-4 w-4" strokeWidth={3} />
                <span className="hidden sm:inline">Admin</span>
              </button>
            )}
            {exportAllowed && activeConversationId && messages.length > 0 && (
              <button
                onClick={handleExport}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-3 py-1.5 text-xs font-bold uppercase neo-shadow-sm neo-press"
                title="Tải JSON toàn bộ hội thoại"
              >
                <Download className="h-4 w-4" strokeWidth={3} />
                Export
              </button>
            )}
            {messages.length > 0 && (
              <button
                onClick={clear}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-3 py-1.5 text-xs font-bold uppercase neo-shadow-sm neo-press"
              >
                <Trash2 className="h-4 w-4" strokeWidth={3} />
                Clear UI
              </button>
            )}
            <button
              onClick={onLogout}
              className="inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-pink-300 px-3 py-1.5 text-xs font-bold uppercase neo-shadow-sm neo-press"
            >
              <LogOut className="h-4 w-4" strokeWidth={3} />
              <span className="hidden sm:inline">Đăng xuất</span>
            </button>
          </div>
        </header>

        {tier === "basic" && (
          <div className="border-b-2 border-black bg-orange-200 px-4 py-2 text-xs font-bold md:px-6">
            <div className="mx-auto flex max-w-4xl items-start gap-2">
              <Crown className="mt-0.5 h-4 w-4 flex-shrink-0 text-yellow-700" strokeWidth={3} />
              <div className="flex-1">
                Tài khoản đang ở tier <b className="uppercase">basic</b> — chỉ trả lời từ dữ liệu Olist.
                Các tính năng <b>web search · upload · export</b> cần admin phê duyệt nâng tier.
              </div>
            </div>
          </div>
        )}

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
          <div className="mx-auto flex max-w-4xl flex-col gap-6">
            {loadingConversation ? (
              <div className="flex justify-center py-10 text-sm font-bold uppercase text-zinc-500">
                Đang tải hội thoại…
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-6 py-12">
                <div className="flex h-20 w-20 items-center justify-center rounded-lg border-2 border-black bg-pink-400 neo-shadow-lg">
                  <Sparkles className="h-10 w-10 text-black" strokeWidth={3} />
                </div>
                <div className="text-center">
                  <h2 className="text-3xl font-black uppercase tracking-tight">
                    Hỏi gì cũng được
                  </h2>
                  <p className="mt-3 inline-block rounded-md border-2 border-black bg-white px-3 py-1 text-sm font-bold neo-shadow-sm">
                    Multi-agent · SQL · KPI · Schema · Web search optional
                  </p>
                </div>
                <div className="w-full max-w-2xl">
                  <SuggestedQuestions onPick={sendMessage} variant="initial" />
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    onRetryWithForceSearch={handleRetryWithForceSearch}
                    onTurnOnToggle={handleTurnOnToggle}
                    webSearchAllowed={webSearchAllowed}
                  />
                ))}
                {!busy && lastAssistantMessage && (
                  <div className="ml-11">
                    <SuggestedQuestions
                      onPick={sendMessage}
                      variant="compact"
                      intent={lastIntent}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <Composer
          busy={busy}
          onSend={sendMessage}
          onStop={stop}
          webSearchEnabled={webSearchEnabled && webSearchAllowed}
          onToggleWebSearch={setWebSearchEnabled}
          conversationId={activeConversationId}
          webSearchAllowed={webSearchAllowed}
        />
      </div>

      <AdminPanel open={adminOpen} onClose={() => setAdminOpen(false)} />
    </div>
  );
}
