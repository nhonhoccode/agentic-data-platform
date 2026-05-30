import { useCallback, useEffect, useState } from "react";
import {
  ShieldCheck,
  Shield,
  Loader2,
  X,
  UserCheck,
  UserX,
  Crown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  adminListUsers,
  adminSetIsAdmin,
  adminSetTier,
  type AdminUser,
  type UserTier,
} from "@/lib/session";

interface AdminPanelProps {
  open: boolean;
  onClose: () => void;
}

const TIER_LABEL: Record<UserTier, string> = {
  basic: "Basic",
  approved: "Approved",
  admin: "Admin",
};

const TIER_DESC: Record<UserTier, string> = {
  basic: "chỉ chat Olist data",
  approved: "+ web search, upload, export",
  admin: "+ quản lý user khác",
};

export function AdminPanel({ open, onClose }: AdminPanelProps) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await adminListUsers());
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void refetch();
  }, [open, refetch]);

  const updateTier = async (u: AdminUser, tier: UserTier) => {
    setBusy(u.username);
    try {
      const next = await adminSetTier(u.username, tier);
      setUsers((prev) => prev.map((x) => (x.username === u.username ? next : x)));
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const updateAdmin = async (u: AdminUser, isAdmin: boolean) => {
    setBusy(u.username);
    try {
      const next = await adminSetIsAdmin(u.username, isAdmin);
      setUsers((prev) => prev.map((x) => (x.username === u.username ? next : x)));
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (!open) return null;

  const filtered = users.filter((u) =>
    u.username.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-8">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-md border-2 border-black bg-yellow-50 neo-shadow-lg">
        <header className="flex items-center justify-between border-b-2 border-black bg-yellow-300 px-4 py-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" strokeWidth={3} />
            <h2 className="text-sm font-black uppercase tracking-tight">
              Quản lý user
            </h2>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md border-2 border-black bg-white neo-shadow-sm neo-press"
            aria-label="Đóng"
          >
            <X className="h-4 w-4" strokeWidth={3} />
          </button>
        </header>

        <div className="border-b-2 border-black bg-white px-4 py-2.5">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Lọc theo username…"
            className="w-full rounded-md border-2 border-black bg-white px-3 py-1.5 text-xs font-medium placeholder:text-zinc-500 focus:outline-none neo-shadow-sm"
          />
        </div>

        {error && (
          <div className="mx-4 mt-3 rounded-md border-2 border-black bg-orange-300 p-2 text-xs font-bold neo-shadow-sm">
            Lỗi: {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 p-8 text-sm font-bold uppercase text-zinc-500">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={3} />
              Đang tải…
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-sm font-medium text-zinc-500">
              {users.length === 0
                ? "Chưa có user nào đăng ký."
                : "Không tìm thấy user khớp."}
            </div>
          ) : (
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="border-b-2 border-black text-left uppercase">
                  <th className="px-2 py-2 font-black">Username</th>
                  <th className="px-2 py-2 font-black">Tier</th>
                  <th className="px-2 py-2 font-black">Admin</th>
                  <th className="px-2 py-2 font-black">Tạo lúc</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => {
                  const updating = busy === u.username;
                  return (
                    <tr
                      key={u.username}
                      className="border-b border-zinc-300 hover:bg-yellow-100"
                    >
                      <td className="px-2 py-2 font-bold">
                        {u.username}
                        {u.is_admin && (
                          <Crown
                            className="ml-1 inline h-3 w-3 text-yellow-600"
                            strokeWidth={3}
                          />
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex gap-1">
                          {(["basic", "approved", "admin"] as UserTier[]).map((t) => (
                            <button
                              key={t}
                              onClick={() => !updating && u.tier !== t && updateTier(u, t)}
                              disabled={updating}
                              className={cn(
                                "rounded-sm border border-black px-2 py-0.5 text-[10px] font-black uppercase disabled:opacity-50",
                                u.tier === t
                                  ? t === "admin"
                                    ? "bg-pink-300 neo-shadow-sm"
                                    : t === "approved"
                                      ? "bg-lime-300 neo-shadow-sm"
                                      : "bg-zinc-200 neo-shadow-sm"
                                  : "bg-white hover:bg-yellow-100",
                              )}
                              title={`${TIER_LABEL[t]} — ${TIER_DESC[t]}`}
                            >
                              {TIER_LABEL[t]}
                            </button>
                          ))}
                        </div>
                      </td>
                      <td className="px-2 py-2">
                        <button
                          onClick={() => !updating && updateAdmin(u, !u.is_admin)}
                          disabled={updating}
                          className={cn(
                            "inline-flex items-center gap-1 rounded-sm border border-black px-1.5 py-0.5 text-[10px] font-black uppercase disabled:opacity-50",
                            u.is_admin ? "bg-pink-300" : "bg-white hover:bg-yellow-100",
                          )}
                        >
                          {u.is_admin ? (
                            <>
                              <UserCheck className="h-3 w-3" strokeWidth={3} />
                              ON
                            </>
                          ) : (
                            <>
                              <UserX className="h-3 w-3" strokeWidth={3} />
                              OFF
                            </>
                          )}
                        </button>
                      </td>
                      <td className="px-2 py-2 font-mono text-[10px] text-zinc-500">
                        {u.created_at
                          ? new Date(u.created_at * 1000).toISOString().slice(0, 16).replace("T", " ")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <footer className="border-t-2 border-black bg-white px-4 py-2 text-[10px] font-medium text-zinc-600">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <Shield className="h-3 w-3" strokeWidth={3} />
              <b>basic</b> = chỉ chat Olist
            </span>
            <span className="inline-flex items-center gap-1">
              <Shield className="h-3 w-3 text-lime-700" strokeWidth={3} />
              <b>approved</b> = + web search + upload + export
            </span>
            <span className="inline-flex items-center gap-1">
              <Crown className="h-3 w-3 text-yellow-700" strokeWidth={3} />
              <b>admin</b> = + quản lý user
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
