import { useCallback, useEffect, useState } from "react";
import {
  createConversation,
  deleteConversation,
  listConversations,
  renameConversation,
  type ConversationMeta,
} from "@/lib/api";

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listConversations();
      setConversations(list);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const create = useCallback(async (title?: string): Promise<ConversationMeta> => {
    const c = await createConversation(title);
    setConversations((prev) => [c, ...prev]);
    return c;
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, []);

  const rename = useCallback(async (id: string, title: string) => {
    await renameConversation(id, title);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c)),
    );
  }, []);

  // Patch a single conversation's metadata locally without a refetch — used
  // when the stream emits `event: conversation` (auto-created on first turn).
  const upsertLocal = useCallback((meta: Partial<ConversationMeta> & { id: string }) => {
    setConversations((prev) => {
      const idx = prev.findIndex((c) => c.id === meta.id);
      if (idx >= 0) {
        const next = prev.slice();
        next[idx] = { ...next[idx], ...meta };
        return next;
      }
      const created: ConversationMeta = {
        id: meta.id,
        title: meta.title ?? "New chat",
        updated_at: meta.updated_at ?? Math.floor(Date.now() / 1000),
        message_count: meta.message_count ?? 0,
      };
      return [created, ...prev];
    });
  }, []);

  return { conversations, loading, error, refetch, create, remove, rename, upsertLocal };
}
