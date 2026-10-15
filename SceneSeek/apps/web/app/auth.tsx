'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

export const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const KEY = 'sceneseek_token';

export function getToken(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type User = { id: string; email: string; name?: string | null; picture?: string | null };
type GoogleId = {
  initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void;
  renderButton: (element: HTMLElement, options: Record<string, string>) => void;
};
declare global { interface Window { google?: { accounts: { id: GoogleId } } } }

function loadGoogleScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) { resolve(); return; }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Google script failed to load'));
    document.head.appendChild(script);
  });
}

export default function AuthButton() {
  const [clientId, setClientId] = useState('');
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState('');
  const slot = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/v1/config`).then(r => r.ok ? r.json() : null).then(cfg => { if (alive && cfg?.google_login) setClientId(cfg.google_client_id); }).catch(() => undefined);
    const token = getToken();
    if (token) {
      fetch(`${API}/v1/me`, { headers: authHeaders() }).then(r => {
        if (r.ok) return r.json();
        try { localStorage.removeItem(KEY); } catch { /* ignore */ }
        return null;
      }).then(u => { if (alive && u) setUser(u); }).catch(() => undefined);
    }
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
            const r = await fetch(`${API}/v1/auth/google`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ credential }) });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Sign-in failed.');
            try { localStorage.setItem(KEY, data.token); } catch { /* ignore */ }
            setUser(data.user); setError('');
          } catch (err) { setError(err instanceof Error ? err.message : 'Sign-in failed.'); }
        },
      });
      window.google.accounts.id.renderButton(slot.current, { theme: 'filled_black', size: 'medium', shape: 'pill', text: 'signin_with' });
    }).catch(() => setError('Could not load Google sign-in.'));
    return () => { cancelled = true; };
  }, [clientId, user]);

  if (!clientId && !user) return null;
  if (user) {
    return (
      <span className="auth-box">
        {user.picture && <img className="auth-avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />}
        <Link href="/history">History</Link>
        <button type="button" className="text-button" onClick={() => { try { localStorage.removeItem(KEY); } catch { /* ignore */ } setUser(null); }}>Sign out</button>
      </span>
    );
  }
  return <span className="auth-box"><div ref={slot} />{error && <small className="auth-error">{error}</small>}</span>;
}
