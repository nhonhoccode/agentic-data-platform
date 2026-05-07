import { useEffect, useRef } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatMessage } from "@/components/ChatMessage";
import { Composer } from "@/components/Composer";
import { Button } from "@/components/ui/button";
import { Sparkles, Trash2 } from "lucide-react";
import { SuggestedQuestions } from "@/components/SuggestedQuestions";

export default function App() {
  const { messages, busy, sendMessage, stop, clear } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const lastAssistantMessage = [...messages].reverse().find((m) => m.role === "assistant" && !m.streaming);
  const lastIntent = lastAssistantMessage?.intent ?? null;

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex items-center justify-between border-b bg-background px-6 py-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <h1 className="text-base font-semibold">Olist AI Data Platform</h1>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">multi-agent · RAG</span>
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clear}>
              <Trash2 className="mr-1.5 h-4 w-4" />
              Xóa hội thoại
            </Button>
          )}
        </div>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-6 py-12">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <div className="text-center">
                <h2 className="text-2xl font-semibold tracking-tight">Hỏi gì cũng được</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Hệ thống multi-agent tự định tuyến SQL · KPI · Schema · Phân tích xu hướng.
                </p>
              </div>
              <div className="w-full max-w-2xl">
                <SuggestedQuestions onPick={sendMessage} variant="initial" />
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {!busy && lastAssistantMessage && (
                <div className="ml-11">
                  <SuggestedQuestions onPick={sendMessage} variant="compact" intent={lastIntent} />
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <Composer busy={busy} onSend={sendMessage} onStop={stop} />
    </div>
  );
}
