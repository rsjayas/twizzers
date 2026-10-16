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

/** Downloads a file from an authenticated admin endpoint (for example a CSV export). */
export async function download(path: string, filename: string): Promise<void> {
  const token = tokenStore.get();
  const res = await fetch(`/admin/api${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, `Download failed (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- types ----
export type Admin = { id: string; email: string; role: string; is_active: boolean; created_at: string | null; last_login_at: string | null; totp_enabled: boolean; permissions: string[] };
export type Paged<T> = { total: number; items: T[] };
export type User = { id: string; name: string | null; phone: string | null; email: string | null; providers: string[]; credits_balance: number; is_blocked: boolean; blocked_reason: string | null; deleted: boolean; created_at: string | null };
export type Creation = { id: string; user_id: string; status: string; rendered_video_url: string | null; thumbnail_url: string | null; share_link_slug: string; recipient_view_count: number; created_at: string | null; poem: string | null };
export type Txn = { id: string; user_id: string; credits: number; amount_inr: number; status: string; note: string | null; cashfree_order_id: string | null; created_at: string | null; paid_at: string | null };
export type UserDetail = User & { poem_count: number; creations: Creation[]; transactions: Txn[] };
export type Stats = {
  totals: { users: number; poems: number; creations: number; shares: number; revenue_inr: number; credits_outstanding: number; open_reports: number };
  creations_by_status: Record<string, number>;
  render_failure_rate: number;
  funnel: { signed_up: number; made_a_poem: number; made_a_video: number; shared: number };
  shares_by_channel: { name: string; count: number }[];
  top_templates: { name: string; count: number }[];
  top_music: { name: string; count: number }[];
  daily: { date: string; signups: number; poems: number; creations: number; shares: number; revenue_inr: number }[];
};
export type Template = { id: string; name: string; category: string; mood_tags: string[]; lottie_file_url: string | null; rive_file_url: string | null; preview_thumbnail_url: string | null; is_active: boolean };
export type Music = { id: string; title: string; artist: string | null; license_source: string | null; mood_tags: string[]; audio_file_url: string; duration_seconds: number | null };
export type Pack = { id: string; label: string; credits: number; price_inr: number; is_active: boolean };
export type Settings = { payments_enabled: boolean; cost_per_story_credits: number; signups_enabled: boolean; welcome_credits: number };
export type Report = {
  id: string; creation_id: string; reason: string; details: string | null; status: string; created_at: string | null;
  handled_by: string | null; handled_at: string | null; resolution_note: string | null;
  creation: { status: string; user_id: string; share_link_slug: string; rendered_video_url: string | null; poem: string | null } | null;
};
export type PoemRow = { id: string; user_id: string; user_name: string | null; source: string; status: string; content: string | null; created_at: string | null };
export type SystemStatus = {
  database_ok: boolean;
  render_service: { configured: boolean; reachable: boolean | null; queued: number | null; running: boolean | null };
  integrations: { claude_api: boolean; firebase_auth: boolean; cashfree: boolean; cashfree_environment: string };
  environment: { auth_dev_bypass: boolean; origin_verify: boolean; cors_origins: string[] };
  settings: Settings;
  attention: { open_reports: number; failed_renders_24h: number; stuck_renders: number };
  warnings: string[];
};
export type AuditRow = { id: string; admin_email: string | null; action: string; target_type: string | null; target_id: string | null; details: unknown; created_at: string | null };
