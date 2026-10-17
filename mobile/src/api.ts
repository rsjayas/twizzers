import { API_BASE } from './config';
import { auth } from './auth';
import type { AppConfig, Creation, GenerateInput, MusicTrack, MyCreation, Poem, Template } from './types';

/** Server error codes turned into sentences a person can act on. */
const MESSAGES: Record<string, string> = {
  signups_closed: 'New accounts are closed right now. Please try again later.',
  account_blocked: 'This account has been blocked. Contact support if you think this is a mistake.',
  account_deleted: 'This account was deleted.',
  email_not_verified: 'Please confirm your email address first.',
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (init.auth !== false) {
    const token = await auth.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: init.method ?? 'GET',
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection.');
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') detail = MESSAGES[data.detail] ?? data.detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  config: () => request<AppConfig>('/config', { auth: false }),
  balance: () => request<{ credits_balance: number }>('/credits/balance'),
  myCreations: () => request<MyCreation[]>('/creations/mine'),
  eraseMe: () => request<{ ok: boolean }>('/auth/me/erase', { method: 'POST', body: { confirm: 'DELETE' } }),
  generatePoem: (input: GenerateInput) => request<Poem>('/poems/generate', { method: 'POST', body: input }),
  writePoem: (content: string) => request<Poem>('/poems/write', { method: 'POST', body: { content } }),
  selectVariant: (poemId: string, variantId: string) =>
    request<Poem>(`/poems/${poemId}/select-variant`, { method: 'POST', body: { variant_id: variantId } }),
  templates: () => request<Template[]>('/templates/', { auth: false }),
  music: () => request<MusicTrack[]>('/music/', { auth: false }),
  createCreation: (poemId: string, templateId: string, musicId: string) =>
    request<Creation>('/creations/', {
      method: 'POST',
      body: { poem_id: poemId, template_id: templateId, music_track_id: musicId },
    }),
  getCreation: (id: string) => request<Creation>(`/creations/${id}`),
  logShare: (creationId: string, channel: string) =>
    request<{ ok: boolean }>('/creations/share-event', { method: 'POST', body: { creation_id: creationId, channel } }),
};
