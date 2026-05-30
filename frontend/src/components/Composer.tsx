import { useEffect, useRef, useState } from "react";
import { Send, Square, Paperclip, Loader2, Globe } from "lucide-react";
import { uploadFile } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  webSearchEnabled: boolean;
  onToggleWebSearch: (enabled: boolean) => void;
  /** Active conversation id — used as draft localStorage key. `null` = new chat. */
  conversationId: string | null;
  /** True if the current user is permitted to use web search (tier ≥ approved). */
  webSearchAllowed: boolean;
}

const DRAFT_KEY = (cid: string | null) => `olist_draft_${cid ?? "_new"}`;

function loadDraft(cid: string | null): string {
  try {
    return window.localStorage.getItem(DRAFT_KEY(cid)) ?? "";
  } catch {
    return "";
  }
}

function saveDraft(cid: string | null, text: string): void {
  try {
    if (text) window.localStorage.setItem(DRAFT_KEY(cid), text);
    else window.localStorage.removeItem(DRAFT_KEY(cid));
  } catch {
    /* ignore */
  }
}

export function Composer({
  busy,
  onSend,
  onStop,
  webSearchEnabled,
  onToggleWebSearch,
  conversationId,
  webSearchAllowed,
}: ComposerProps) {
  const [text, setText] = useState<string>(() => loadDraft(conversationId));
  const [uploading, setUploading] = useState(false);
  const [uploadInfo, setUploadInfo] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // When the active conversation changes, restore that conversation's draft.
  useEffect(() => {
    setText(loadDraft(conversationId));
  }, [conversationId]);

  // Persist on every keystroke (debounce isn't needed — localStorage is fast).
  useEffect(() => {
    saveDraft(conversationId, text);
  }, [conversationId, text]);

  const handleSend = () => {
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
    saveDraft(conversationId, "");
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadInfo(null);
    const result = await uploadFile(file);
    setUploading(false);
    if (result.ok) {
      setUploadInfo(`✓ Đã nạp ${result.rows_loaded} dòng vào ${result.table}`);
    } else {
      setUploadInfo(`✗ ${result.detail}`);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="border-t-2 border-black bg-yellow-100 p-4">
      {uploadInfo && (
        <div className="mb-2 inline-block rounded-md border-2 border-black bg-lime-300 px-3 py-1 text-xs font-bold neo-shadow-sm">
          {uploadInfo}
        </div>
      )}
      <div className="flex items-end gap-2">
        <input ref={fileInputRef} type="file" accept=".csv,.txt,.pdf" className="hidden" onChange={handleUpload} />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex h-11 w-11 items-center justify-center rounded-md border-2 border-black bg-white neo-shadow-sm neo-press disabled:opacity-50"
          aria-label="Upload file"
          title="Đính kèm CSV / PDF"
        >
          {uploading ? (
            <Loader2 className="h-5 w-5 animate-spin" strokeWidth={3} />
          ) : (
            <Paperclip className="h-5 w-5" strokeWidth={3} />
          )}
        </button>

        <button
          type="button"
          onClick={() => webSearchAllowed && onToggleWebSearch(!webSearchEnabled)}
          disabled={busy || !webSearchAllowed}
          className={cn(
            "flex h-11 items-center justify-center gap-1.5 rounded-md border-2 border-black px-3 text-xs font-black uppercase neo-shadow-sm neo-press disabled:opacity-50",
            webSearchEnabled && webSearchAllowed
              ? "bg-lime-300"
              : !webSearchAllowed
                ? "bg-zinc-200 cursor-not-allowed"
                : "bg-white",
          )}
          aria-pressed={webSearchEnabled && webSearchAllowed}
          title={
            !webSearchAllowed
              ? "Tính năng web search cần admin phê duyệt. Liên hệ admin để bật."
              : webSearchEnabled
                ? "Web search ON — agent có thể tra Internet cho câu hỏi e-commerce/Olist"
                : "Web search OFF — agent chỉ trả lời từ dữ liệu Olist. Click để bật."
          }
        >
          <Globe className="h-4 w-4" strokeWidth={3} />
          {webSearchAllowed && webSearchEnabled && (
            <span className="hidden sm:inline">ON</span>
          )}
        </button>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder={
            webSearchEnabled
              ? "Hỏi tự nhiên — có thể tra Internet về e-commerce / KPI..."
              : "Hỏi về KPI, doanh thu, danh mục, schema..."
          }
          rows={1}
          className="min-h-[44px] flex-1 resize-none rounded-md border-2 border-black bg-white px-3 py-2.5 text-sm font-medium placeholder:text-zinc-500 focus:outline-none focus:ring-0 neo-shadow-sm"
        />

        {busy ? (
          <button
            onClick={onStop}
            className={cn(
              "flex h-11 items-center justify-center gap-1.5 rounded-md border-2 border-black bg-red-400 px-4 text-sm font-black uppercase neo-shadow-sm neo-press",
            )}
          >
            <Square className="h-4 w-4" strokeWidth={3} />
            Stop
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!text.trim()}
            className={cn(
              "flex h-11 items-center justify-center gap-1.5 rounded-md border-2 border-black bg-pink-400 px-4 text-sm font-black uppercase neo-shadow-sm neo-press disabled:opacity-40 disabled:cursor-not-allowed",
            )}
          >
            <Send className="h-4 w-4" strokeWidth={3} />
            Send
          </button>
        )}
      </div>
    </div>
  );
}
