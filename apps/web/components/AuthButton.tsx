'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AUTH_EVENT, apiFetch, clearToken, getToken, setToken } from '../lib/api';
import type { PublicConfig, User } from '../lib/types';

type GoogleId = {
  initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void;
  renderButton: (element: HTMLElement, options: Record<string, string>) => void;
};
declare global { interface Window { google?: { accounts: { id: GoogleId } } } }

let scriptPromise: Promise<void> | null = null;
function loadGoogleScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => { scriptPromise = null; reject(new Error('Google script failed to load')); };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

/** Shared sign-in state for components that need to know who is logged in. */
export function useUser(): { user: User | null; ready: boolean } {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(() => {
    if (!getToken()) { setUser(null); setReady(true); return; }
    apiFetch<User>('/v1/me').then(setUser).catch(() => setUser(null)).finally(() => setReady(true));
  }, []);
  useEffect(() => {
    refresh();
    window.addEventListener(AUTH_EVENT, refresh);
    return () => window.removeEventListener(AUTH_EVENT, refresh);
  }, [refresh]);
  return { user, ready };
}

export default function AuthButton() {
  const [clientId, setClientId] = useState('');
  const [error, setError] = useState('');
  const { user } = useUser();
  const slot = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    apiFetch<PublicConfig>('/v1/config').then(cfg => { if (alive && cfg.google_login) setClientId(cfg.google_client_id); }).catch(() => undefined);
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!clientId || user) return;
    let cancelled = false;
    loadGoogleScript().then(() => {
      if (cancelled || !slot.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async ({ credential }) => {
          try {
            const data = await apiFetch<{ token: string; user: User }>('/v1/auth/google', {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ credential }), retries: 1,
            });
            setToken(data.token); setError('');
          } catch (err) { setError(err instanceof Error ? err.message : 'Sign-in failed.'); }
        },
      });
      window.google.accounts.id.renderButton(slot.current, { theme: 'filled_black', size: 'medium', shape: 'pill', text: 'signin_with' });
    }).catch(() => setError('Could not load Google sign-in.'));
    return () => { cancelled = true; };
  }, [clientId, user]);

  if (user) {
    return (
      <span className="auth-box">
        {user.picture && <img className="auth-avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />}
        <Link href="/history">History</Link>
        <button type="button" className="text-button" onClick={clearToken}>Sign out</button>
      </span>
    );
  }
  if (!clientId) return null;
  return <span className="auth-box"><div ref={slot} />{error && <small className="auth-error" role="alert">{error}</small>}</span>;
}

