import type { User } from './types';

export const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const TOKEN_KEY = 'sceneseek_token';
export const AUTH_EVENT = 'sceneseek:auth';

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string): void {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* storage unavailable (private mode) */ }
  notifyAuthChange();
}
export function clearToken(): void {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  notifyAuthChange();
}
function notifyAuthChange(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT));
}
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  status: number;
  retryAfter?: number;
  constructor(message: string, status = 0, retryAfter?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

type Options = Omit<RequestInit, 'signal'> & { timeoutMs?: number; retries?: number; signal?: AbortSignal };

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));

/** fetch + JSON with auth header, timeout, friendly errors and retry of idempotent GETs (free hosts cold-start). */
export async function apiFetch<T = unknown>(path: string, options: Options = {}): Promise<T> {
  const { timeoutMs = 30_000, retries, signal, headers, ...init } = options;
  const method = (init.method || 'GET').toUpperCase();
  const attempts = 1 + (retries ?? (method === 'GET' ? 2 : 0));
  let lastError: ApiError = new ApiError('Request failed.');
  for (let attempt = 0; attempt < attempts; attempt++) {
    const controller = new AbortController();
    const onAbort = () => controller.abort();
    signal?.addEventListener('abort', onAbort);
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${API}${path}`, {
        ...init, cache: 'no-store', signal: controller.signal, headers: { ...authHeaders(), ...(headers as Record<string, string> | undefined) },
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok) return data as T;
      const detail = typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}).`;
      const retryAfter = Number(response.headers.get('Retry-After')) || undefined;
      if (response.status === 401 && getToken()) clearToken();
      lastError = new ApiError(detail, response.status, retryAfter);
      if (![502, 503, 504].includes(response.status)) throw lastError;
    } catch (err) {
      if (err instanceof ApiError && ![502, 503, 504].includes(err.status)) throw err;
      if (signal?.aborted) throw new ApiError('Cancelled.', 0);
      if (!(err instanceof ApiError)) {
        lastError = new ApiError(controller.signal.aborted
          ? 'The server took too long to respond. It may be waking up — please try again.'
          : 'Cannot reach the server. Check your connection (or that the API is running) and try again.');
      }
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    }
    if (attempt < attempts - 1) await sleep(1500 * (attempt + 1));
  }
  throw lastError;
}

export const getMe = () => apiFetch<User>('/v1/me');

export function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
export function friendlyDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
