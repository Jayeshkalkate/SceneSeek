'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import AuthButton, { API, authHeaders, getToken } from '../auth';

type Item = { job_id: string; status: string; created_at: string; title?: string | null; title_id?: string | null; band?: string | null };

export default function HistoryPage() {
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) { setError('Sign in with Google to see your past searches.'); return; }
    fetch(`${API}/v1/me/history`, { headers: authHeaders(), cache: 'no-store' })
      .then(async r => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Could not load history.'); return d; })
      .then(d => setItems(d.items || []))
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load history.'));
  }, []);

  return <main className="shell subpage-shell"><header className="topbar"><Link href="/" className="brand"><Image src="/sceneseek-logo.png" width={56} height={56} alt="" unoptimized /><span className="brand-word">Scene<span>Seek</span></span></Link><nav className="nav-links"><AuthButton /><Link href="/" className="back-link">← Back to search</Link></nav></header>
    <section className="stats-hero"><span className="section-kicker">YOUR SEARCHES</span><h1>History</h1><p>Only the result summary is kept; the uploaded file itself is deleted after processing.</p></section>
    {error && <div className="error-message stats-error">{error}</div>}
    {!error && !items && <div className="subpage-state"><span className="spinner" /><p>Loading…</p></div>}
    {items && items.length === 0 && <div className="subpage-state"><p>No searches yet.</p></div>}
    {items && items.length > 0 && <div className="table-scroll"><table><thead><tr><th>When</th><th>Top match</th><th>Confidence</th><th>Status</th></tr></thead><tbody>{items.map(item => <tr key={item.job_id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.title ? (item.title_id ? <Link href={`/t/${encodeURIComponent(item.title_id)}`}>{item.title}</Link> : item.title) : '—'}</td><td>{item.band || '—'}</td><td>{item.status}</td></tr>)}</tbody></table></div>}
    <footer className="footer compact-footer"><Link href="/" className="footer-brand"><span className="brand-word">Scene<span>Seek</span></span><small>SEE IT. SEEK IT. FIND IT.</small></Link><p>SceneSeek · Free-tier-first entertainment search.</p></footer></main>;
}
