const TOKEN_KEY = 'tweezers_admin_token';

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = tokenStore.get();
  const res = await fetch(`/admin/api${path}`, {
    method: init.method ?? 'GET',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (res.status === 401 && path !== '/login') onUnauthorized();
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = data.detail[0].msg;
    } catch { /* keep the generic message */ }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

// ---- types ----
export type Admin = { id: string; email: string; role: string; is_active: boolean; created_at: string | null; last_login_at: string | null; permissions: string[] };
export type Paged<T> = { total: number; items: T[] };
export type User = { id: string; name: string | null; phone: string | null; email: string | null; providers: string[]; credits_balance: number; created_at: string | null };
export type Creation = { id: string; user_id: string; status: string; rendered_video_url: string | null; thumbnail_url: string | null; share_link_slug: string; recipient_view_count: number; created_at: string | null; poem: string | null };
export type Txn = { id: string; user_id: string; credits: number; amount_inr: number; status: string; note: string | null; cashfree_order_id: string | null; created_at: string | null; paid_at: string | null };
export type UserDetail = User & { poem_count: number; creations: Creation[]; transactions: Txn[] };
export type Stats = {
  totals: { users: number; poems: number; creations: number; shares: number; revenue_inr: number; credits_outstanding: number };
  creations_by_status: Record<string, number>;
  daily: { date: string; signups: number; poems: number; creations: number; revenue_inr: number }[];
};
export type Template = { id: string; name: string; category: string; mood_tags: string[]; lottie_file_url: string | null; rive_file_url: string | null; preview_thumbnail_url: string | null; is_active: boolean };
export type Music = { id: string; title: string; artist: string | null; license_source: string | null; mood_tags: string[]; audio_file_url: string; duration_seconds: number | null };
export type Pack = { id: string; label: string; credits: number; price_inr: number; is_active: boolean };
export type Settings = { payments_enabled: boolean; cost_per_story_credits: number };
export type AuditRow = { id: string; admin_email: string | null; action: string; target_type: string | null; target_id: string | null; details: unknown; created_at: string | null };
