// Lightweight session token storage shared by the auth pages and the chat API
// client. Token lives in localStorage so it survives full page reloads.

const TOKEN_KEY = "olist_ui_token";
const USER_KEY = "olist_ui_user";
const META_KEY = "olist_ui_meta";

export type UserTier = "basic" | "approved" | "admin";

export interface StoredSession {
  token: string;
  username: string;
  tier?: UserTier;
  is_admin?: boolean;
  features?: string[];
}

export function getStoredSession(): StoredSession | null {
  try {
    const token = window.localStorage.getItem(TOKEN_KEY);
    const username = window.localStorage.getItem(USER_KEY);
    if (!token || !username) return null;
    const metaRaw = window.localStorage.getItem(META_KEY);
    let meta: Partial<StoredSession> = {};
    if (metaRaw) {
      try {
        meta = JSON.parse(metaRaw) as Partial<StoredSession>;
      } catch {
        /* ignore */
      }
    }
    return { token, username, ...meta };
  } catch {
    return null;
  }
}

export function setStoredSession(session: StoredSession): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, session.token);
    window.localStorage.setItem(USER_KEY, session.username);
    const meta = {
      tier: session.tier ?? "basic",
      is_admin: !!session.is_admin,
      features: session.features ?? [],
    };
    window.localStorage.setItem(META_KEY, JSON.stringify(meta));
  } catch {
    /* localStorage disabled — non-fatal */
  }
}

export function clearStoredSession(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
    window.localStorage.removeItem(META_KEY);
  } catch {
    /* ignore */
  }
}

export function hasFeature(session: StoredSession | null, feature: string): boolean {
  if (!session) return false;
  return (session.features ?? []).includes(feature);
}

export function authHeaders(): Record<string, string> {
  const session = getStoredSession();
  if (!session) return {};
  return { Authorization: `Bearer ${session.token}` };
}

const PROXY_BASE = "/ui/proxy";

export interface LoginResponse {
  token: string;
  username: string;
  expires_in: number;
  tier?: UserTier;
  is_admin?: boolean;
  features?: string[];
}

export async function loginRequest(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const resp = await fetch(`${PROXY_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const json = await resp.json();
  if (!resp.ok) {
    throw new Error(json.detail ?? `HTTP ${resp.status}`);
  }
  return json as LoginResponse;
}

export async function registerRequest(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const resp = await fetch(`${PROXY_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const json = await resp.json();
  if (!resp.ok) {
    throw new Error(json.detail ?? `HTTP ${resp.status}`);
  }
  return json as LoginResponse;
}

export interface MeResponse {
  username: string;
  tier: UserTier;
  is_admin: boolean;
  features: string[];
}

export async function verifyMe(): Promise<MeResponse | null> {
  const session = getStoredSession();
  if (!session) return null;
  try {
    const resp = await fetch(`${PROXY_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${session.token}` },
    });
    if (!resp.ok) return null;
    return (await resp.json()) as MeResponse;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Admin endpoints
// ---------------------------------------------------------------------------

export interface AdminUser {
  username: string;
  tier: UserTier;
  is_admin: boolean;
  created_at: number;
}

export async function adminListUsers(): Promise<AdminUser[]> {
  const session = getStoredSession();
  if (!session) throw new Error("not_authenticated");
  const resp = await fetch(`${PROXY_BASE}/admin/users`, {
    headers: { Authorization: `Bearer ${session.token}` },
  });
  if (!resp.ok) throw new Error(`adminListUsers HTTP ${resp.status}`);
  const json = await resp.json();
  return (json.users as AdminUser[]) ?? [];
}

export async function adminSetTier(
  username: string,
  tier: UserTier,
): Promise<AdminUser> {
  const session = getStoredSession();
  if (!session) throw new Error("not_authenticated");
  const resp = await fetch(
    `${PROXY_BASE}/admin/users/${encodeURIComponent(username)}/tier`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.token}`,
      },
      body: JSON.stringify({ tier }),
    },
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${resp.status}`);
  }
  const json = await resp.json();
  return json.user as AdminUser;
}

export async function adminSetIsAdmin(
  username: string,
  isAdmin: boolean,
): Promise<AdminUser> {
  const session = getStoredSession();
  if (!session) throw new Error("not_authenticated");
  const resp = await fetch(
    `${PROXY_BASE}/admin/users/${encodeURIComponent(username)}/admin`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.token}`,
      },
      body: JSON.stringify({ is_admin: isAdmin }),
    },
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${resp.status}`);
  }
  const json = await resp.json();
  return json.user as AdminUser;
}
