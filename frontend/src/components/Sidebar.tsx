import { useEffect, useMemo, useState } from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  X,
  Menu,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConversationMeta } from "@/lib/api";

interface SidebarProps {
  conversations: ConversationMeta[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string | null) => void;
  onNewChat: () => void;
  onDelete: (id: string) => Promise<void> | void;
  onRename: (id: string, title: string) => Promise<void> | void;
  mobileOpen: boolean;
  onMobileClose: () => void;
  desktopCollapsed: boolean;
  onToggleDesktopCollapsed: () => void;
}

function relativeTime(unix: number): string {
  const now = Math.floor(Date.now() / 1000);
  const diff = Math.max(0, now - unix);
  if (diff < 60) return "vừa xong";
  if (diff < 3600) return `${Math.floor(diff / 60)}p`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} ngày`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400 / 7)} tuần`;
  return `${Math.floor(diff / (86400 * 30))} tháng`;
}

export function Sidebar({
  conversations,
  activeId,
  loading,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  mobileOpen,
  onMobileClose,
  desktopCollapsed,
  onToggleDesktopCollapsed,
}: SidebarProps) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [search, setSearch] = useState("");

  const handleDelete = async (id: string) => {
    await onDelete(id);
    setConfirmDelete(null);
  };

  const startRename = (c: ConversationMeta) => {
    setRenameId(c.id);
    setRenameValue(c.title);
  };

  const commitRename = async () => {
    if (renameId && renameValue.trim()) {
      await onRename(renameId, renameValue.trim());
    }
    setRenameId(null);
    setRenameValue("");
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => (c.title || "").toLowerCase().includes(q));
  }, [conversations, search]);

  // --- Desktop collapsed rail ---
  if (desktopCollapsed) {
    return (
      <>
        {mobileOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/40 md:hidden"
            onClick={onMobileClose}
            aria-hidden
          />
        )}
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r-2 border-black bg-yellow-50 transition-transform md:relative md:translate-x-0 md:w-12",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          {/* Mobile: show full sidebar even when desktop is collapsed */}
          {mobileOpen ? (
            <FullSidebarBody
              conversations={conversations}
              filtered={filtered}
              activeId={activeId}
              loading={loading}
              onSelect={onSelect}
              onNewChat={onNewChat}
              onMobileClose={onMobileClose}
              onToggleDesktopCollapsed={onToggleDesktopCollapsed}
              desktopCollapsed={desktopCollapsed}
              confirmDelete={confirmDelete}
              setConfirmDelete={setConfirmDelete}
              handleDelete={handleDelete}
              renameId={renameId}
              renameValue={renameValue}
              setRenameValue={setRenameValue}
              startRename={startRename}
              commitRename={commitRename}
              setRenameId={setRenameId}
              search={search}
              setSearch={setSearch}
            />
          ) : (
            // Desktop collapsed rail (md+)
            <div className="hidden md:flex flex-col items-center gap-2 py-3">
              <button
                onClick={onToggleDesktopCollapsed}
                className="flex h-9 w-9 items-center justify-center rounded-md border-2 border-black bg-white neo-shadow-sm neo-press"
                aria-label="Mở sidebar"
                title="Mở sidebar"
              >
                <ChevronRight className="h-4 w-4" strokeWidth={3} />
              </button>
              <button
                onClick={onNewChat}
                className="flex h-9 w-9 items-center justify-center rounded-md border-2 border-black bg-pink-400 neo-shadow-sm neo-press"
                aria-label="New chat"
                title="New chat"
              >
                <Plus className="h-4 w-4" strokeWidth={3} />
              </button>
              <div className="my-1 h-px w-6 bg-black/30" />
              <span
                className="mt-2 text-[9px] font-black uppercase tracking-widest text-zinc-500"
                style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
              >
                HỘI THOẠI
              </span>
            </div>
          )}
        </aside>
      </>
    );
  }

  // --- Expanded sidebar ---
  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onMobileClose}
          aria-hidden
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r-2 border-black bg-yellow-50 transition-transform md:relative md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <FullSidebarBody
          conversations={conversations}
          filtered={filtered}
          activeId={activeId}
          loading={loading}
          onSelect={onSelect}
          onNewChat={onNewChat}
          onMobileClose={onMobileClose}
          onToggleDesktopCollapsed={onToggleDesktopCollapsed}
          desktopCollapsed={desktopCollapsed}
          confirmDelete={confirmDelete}
          setConfirmDelete={setConfirmDelete}
          handleDelete={handleDelete}
          renameId={renameId}
          renameValue={renameValue}
          setRenameValue={setRenameValue}
          startRename={startRename}
          commitRename={commitRename}
          setRenameId={setRenameId}
          search={search}
          setSearch={setSearch}
        />
      </aside>
    </>
  );
}

interface FullBodyProps {
  conversations: ConversationMeta[];
  filtered: ConversationMeta[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string | null) => void;
  onNewChat: () => void;
  onMobileClose: () => void;
  onToggleDesktopCollapsed: () => void;
  desktopCollapsed: boolean;
  confirmDelete: string | null;
  setConfirmDelete: (id: string | null) => void;
  handleDelete: (id: string) => Promise<void>;
  renameId: string | null;
  renameValue: string;
  setRenameValue: (v: string) => void;
  startRename: (c: ConversationMeta) => void;
  commitRename: () => Promise<void>;
  setRenameId: (id: string | null) => void;
  search: string;
  setSearch: (s: string) => void;
}

function FullSidebarBody(p: FullBodyProps) {
  return (
    <>
      <div className="flex items-center justify-between border-b-2 border-black bg-yellow-300 px-3 py-2.5">
        <span className="text-xs font-black uppercase tracking-tight">Hội thoại</span>
        <div className="flex items-center gap-1">
          <button
            className="hidden md:flex h-7 w-7 items-center justify-center rounded-md border-2 border-black bg-white neo-shadow-sm neo-press"
            onClick={p.onToggleDesktopCollapsed}
            aria-label="Thu sidebar"
            title="Thu sidebar"
          >
            <ChevronLeft className="h-4 w-4" strokeWidth={3} />
          </button>
          <button
            className="md:hidden flex h-7 w-7 items-center justify-center rounded-md border-2 border-black bg-white neo-shadow-sm neo-press"
            onClick={p.onMobileClose}
            aria-label="Đóng sidebar"
          >
            <X className="h-4 w-4" strokeWidth={3} />
          </button>
        </div>
      </div>

      <div className="border-b-2 border-black p-3">
        <button
          onClick={p.onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border-2 border-black bg-pink-400 px-3 py-2 text-xs font-black uppercase neo-shadow neo-press"
        >
          <Plus className="h-4 w-4" strokeWidth={3} />
          New chat
        </button>
        {p.conversations.length > 0 && (
          <div className="mt-2 flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-2 py-1.5 neo-shadow-sm">
            <Search className="h-3.5 w-3.5 text-zinc-500" strokeWidth={3} />
            <input
              type="text"
              value={p.search}
              onChange={(e) => p.setSearch(e.target.value)}
              placeholder="Tìm hội thoại…"
              className="w-full bg-transparent text-xs font-medium placeholder:text-zinc-400 focus:outline-none"
            />
            {p.search && (
              <button
                onClick={() => p.setSearch("")}
                className="text-zinc-500 hover:text-black"
                aria-label="Xoá"
              >
                <X className="h-3 w-3" strokeWidth={3} />
              </button>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {p.loading ? (
          <div className="flex items-center justify-center gap-2 p-4 text-xs font-bold uppercase text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={3} />
            Đang tải…
          </div>
        ) : p.filtered.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs font-medium text-zinc-500">
            {p.conversations.length === 0
              ? "Chưa có chat. Bấm + New chat để bắt đầu."
              : "Không tìm thấy hội thoại nào khớp."}
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {p.filtered.map((c) => {
              const active = c.id === p.activeId;
              const pendingDelete = p.confirmDelete === c.id;
              const isRenaming = p.renameId === c.id;
              return (
                <li key={c.id}>
                  <div
                    className={cn(
                      "group flex items-start gap-2 rounded-md border-2 border-black px-2 py-2 cursor-pointer neo-shadow-sm",
                      active ? "bg-pink-200" : "bg-white hover:bg-yellow-100",
                    )}
                    onClick={() => !isRenaming && p.onSelect(c.id)}
                    onDoubleClick={(e) => {
                      e.preventDefault();
                      p.startRename(c);
                    }}
                  >
                    <MessageSquare
                      className="mt-0.5 h-4 w-4 flex-shrink-0"
                      strokeWidth={3}
                    />
                    <div className="min-w-0 flex-1">
                      {isRenaming ? (
                        <input
                          autoFocus
                          value={p.renameValue}
                          onChange={(e) => p.setRenameValue(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void p.commitRename();
                            if (e.key === "Escape") p.setRenameId(null);
                          }}
                          onBlur={() => void p.commitRename()}
                          className="w-full rounded-sm border-2 border-black bg-white px-1.5 py-0.5 text-xs font-bold focus:outline-none"
                        />
                      ) : (
                        <div className="truncate text-xs font-bold leading-tight">
                          {c.title || "(no title)"}
                        </div>
                      )}
                      <div className="mt-0.5 text-[10px] font-medium uppercase text-zinc-500">
                        {relativeTime(c.updated_at)} · {c.message_count} msg
                      </div>
                    </div>
                    {pendingDelete ? (
                      <div className="flex flex-col gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            void p.handleDelete(c.id);
                          }}
                          className="rounded-sm border border-black bg-red-400 px-1.5 py-0.5 text-[9px] font-black uppercase neo-press"
                        >
                          Xóa
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            p.setConfirmDelete(null);
                          }}
                          className="rounded-sm border border-black bg-white px-1.5 py-0.5 text-[9px] font-bold uppercase neo-press"
                        >
                          Hủy
                        </button>
                      </div>
                    ) : !isRenaming ? (
                      <div className="hidden flex-col gap-1 group-hover:flex">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            p.startRename(c);
                          }}
                          className="flex h-5 w-5 items-center justify-center rounded-sm text-zinc-600 hover:bg-yellow-200 hover:text-black"
                          aria-label="Đổi tên"
                          title="Đổi tên (hoặc nháy đúp tiêu đề)"
                        >
                          <Pencil className="h-3 w-3" strokeWidth={3} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            p.setConfirmDelete(c.id);
                          }}
                          className="flex h-5 w-5 items-center justify-center rounded-sm text-zinc-600 hover:bg-red-200 hover:text-red-700"
                          aria-label="Xoá"
                        >
                          <Trash2 className="h-3 w-3" strokeWidth={3} />
                        </button>
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}

interface SidebarToggleProps {
  onClick: () => void;
}

export function SidebarToggle({ onClick }: SidebarToggleProps) {
  return (
    <button
      className="md:hidden flex h-9 w-9 items-center justify-center rounded-md border-2 border-black bg-white neo-shadow-sm neo-press"
      onClick={onClick}
      aria-label="Mở sidebar"
    >
      <Menu className="h-5 w-5" strokeWidth={3} />
    </button>
  );
}

const COLLAPSE_KEY = "olist_sidebar_collapsed";

export function useSidebarCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);
  return [collapsed, () => setCollapsed((c) => !c)];
}
