import { useState } from "react";
import { Sparkles, LogIn, UserPlus, AlertTriangle, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  loginRequest,
  registerRequest,
  setStoredSession,
  type LoginResponse,
} from "@/lib/session";

type Mode = "login" | "register";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_credentials: "Sai username hoặc password.",
  missing_or_invalid_session: "Session hết hạn — đăng nhập lại nhé.",
  username_taken: "Username đã có người dùng.",
  username_reserved: "Username này dành riêng cho admin.",
};

function humanizeError(raw: string): string {
  if (!raw) return "Lỗi không xác định.";
  return ERROR_MESSAGES[raw] ?? raw;
}

interface LoginProps {
  onSuccess: (session: {
    token: string;
    username: string;
    tier?: "basic" | "approved" | "admin";
    is_admin?: boolean;
    features?: string[];
  }) => void;
  onBack: () => void;
  initialMode?: Mode;
}

export function Login({ onSuccess, onBack, initialMode = "login" }: LoginProps) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isLogin = mode === "login";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const fn = isLogin ? loginRequest : registerRequest;
      const resp: LoginResponse = await fn(username.trim(), password);
      const next = {
        token: resp.token,
        username: resp.username,
        tier: resp.tier,
        is_admin: resp.is_admin,
        features: resp.features,
      };
      setStoredSession(next);
      onSuccess(next);
    } catch (err) {
      setError(humanizeError((err as Error).message ?? ""));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-yellow-100 px-6 py-12">
      <div className="w-full max-w-md">
        <button
          onClick={onBack}
          className="mb-4 inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-3 py-1.5 text-xs font-bold uppercase neo-shadow-sm neo-press"
        >
          <ArrowLeft className="h-4 w-4" strokeWidth={3} />
          Trang chủ
        </button>

        <div className="rounded-md border-2 border-black bg-white p-6 neo-shadow">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-md border-2 border-black bg-pink-400 neo-shadow-sm">
              <Sparkles className="h-6 w-6 text-black" strokeWidth={3} />
            </div>
            <div>
              <h1 className="text-xl font-black uppercase tracking-tight">
                {isLogin ? "Đăng nhập" : "Tạo tài khoản"}
              </h1>
              <p className="text-xs font-medium text-zinc-600">
                Olist AI Data Platform
              </p>
            </div>
          </div>

          <div className="mb-4 flex gap-2 rounded-md border-2 border-black bg-yellow-100 p-1 neo-shadow-sm">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={cn(
                "flex-1 rounded-sm px-3 py-1.5 text-xs font-bold uppercase",
                isLogin
                  ? "bg-pink-400 border-2 border-black neo-shadow-sm"
                  : "bg-transparent text-zinc-600",
              )}
            >
              <LogIn className="mr-1 inline h-3.5 w-3.5" strokeWidth={3} />
              Đăng nhập
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              className={cn(
                "flex-1 rounded-sm px-3 py-1.5 text-xs font-bold uppercase",
                !isLogin
                  ? "bg-pink-400 border-2 border-black neo-shadow-sm"
                  : "bg-transparent text-zinc-600",
              )}
            >
              <UserPlus className="mr-1 inline h-3.5 w-3.5" strokeWidth={3} />
              Tạo TK
            </button>
          </div>

          <form onSubmit={submit} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs font-bold uppercase tracking-tight">
              Username
              <input
                type="text"
                autoComplete="username"
                autoFocus
                disabled={busy}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={isLogin ? "admin" : "ten-cua-ban"}
                className="rounded-md border-2 border-black bg-white px-3 py-2 text-sm font-medium normal-case neo-shadow-sm focus:outline-none focus:bg-yellow-50"
                minLength={isLogin ? 1 : 3}
                maxLength={32}
                required
              />
              {!isLogin && (
                <span className="text-[10px] font-medium normal-case text-zinc-500">
                  3-32 ký tự, chỉ chữ/số/._-
                </span>
              )}
            </label>

            <label className="flex flex-col gap-1 text-xs font-bold uppercase tracking-tight">
              Password
              <input
                type="password"
                autoComplete={isLogin ? "current-password" : "new-password"}
                disabled={busy}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isLogin ? "••••••" : "tối thiểu 6 ký tự"}
                className="rounded-md border-2 border-black bg-white px-3 py-2 text-sm font-medium normal-case neo-shadow-sm focus:outline-none focus:bg-yellow-50"
                minLength={isLogin ? 1 : 6}
                maxLength={256}
                required
              />
            </label>

            {error && (
              <div className="flex items-start gap-2 rounded-md border-2 border-black bg-orange-300 p-2 text-xs font-bold text-black neo-shadow-sm">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" strokeWidth={3} />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={busy || !username || !password}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-md border-2 border-black bg-pink-400 px-4 py-2.5 text-sm font-black uppercase neo-shadow neo-press disabled:cursor-not-allowed disabled:bg-zinc-200"
            >
              {busy ? (
                "Đang xử lý…"
              ) : isLogin ? (
                <>
                  <LogIn className="h-4 w-4" strokeWidth={3} />
                  Đăng nhập
                </>
              ) : (
                <>
                  <UserPlus className="h-4 w-4" strokeWidth={3} />
                  Tạo tài khoản
                </>
              )}
            </button>
          </form>

        </div>
      </div>
    </div>
  );
}
