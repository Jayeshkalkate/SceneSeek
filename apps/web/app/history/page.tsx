'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import SiteFooter from '../../components/SiteFooter';
import SiteHeader from '../../components/SiteHeader';
import { useUser } from '../../components/AuthButton';
import { apiFetch, clearToken, friendlyDate } from '../../lib/api';
import type { HistoryItem } from '../../lib/types';

export default function HistoryPage() {
  const { user, ready } = useUser();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<'clear' | 'account' | null>(null);

  const load = useCallback(() => {
    setError('');
    apiFetch<{ items: HistoryItem[] }>('/v1/me/history?limit=50')
      .then(d => setItems(d.items || []))
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load history.'));
  }, []);

  useEffect(() => { if (ready && user) load(); }, [ready, user, load]);

  const removeOne = async (id: string) => {
    setBusy(true); setError('');
    try { await apiFetch(`/v1/me/history/${encodeURIComponent(id)}`, { method: 'DELETE' }); setItems(prev => (prev || []).filter(i => i.job_id !== id)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not delete that search.'); }
    finally { setBusy(false); }
  };

  const confirmed = async () => {
    const action = confirm;
    setConfirm(null);
    if (!action) return;
    setBusy(true); setError('');
    try {
      if (action === 'clear') { await apiFetch('/v1/me/history/clear', { method: 'DELETE' }); setItems([]); }
      else { await apiFetch('/v1/me/delete', { method: 'DELETE' }); clearToken(); setItems(null); }
    } catch (err) { setError(err instanceof Error ? err.message : 'That action failed. Please try again.'); }
    finally { setBusy(false); }
  };

  return <main className="shell subpage-shell" id="main"><SiteHeader />
    <section className="stats-hero"><span className="section-kicker">YOUR SEARCHES</span><h1>History</h1><p>Only the result summary is kept; the uploaded file itself is deleted after processing. You can remove any search, or your whole account, at any time.</p></section>
    {error && <div className="error-message stats-error" role="alert">{error}</div>}
    {ready && !user && <div className="subpage-state"><p>Sign in with Google to see your past searches.</p><Link href="/" className="primary-button link-button">Go to the home page</Link></div>}
    {user && !items && !error && <div className="subpage-state"><span className="spinner" /><p>Loading…</p></div>}
    {user && items && items.length === 0 && <div className="subpage-state"><p>No searches yet.</p><Link href="/" className="primary-button link-button">Identify a scene ↗</Link></div>}
    {user && items && items.length > 0 && <>
      <div className="table-scroll"><table><thead><tr><th>When</th><th>Top match</th><th>Confidence</th><th>Status</th><th><span className="visually-hidden">Actions</span></th></tr></thead><tbody>
        {items.map(item => <tr key={item.job_id}>
          <td>{friendlyDate(item.created_at)}</td>
          <td>{item.title ? (item.title_id ? <Link href={`/t/${encodeURIComponent(item.title_id)}`}>{item.title}</Link> : item.title) : '—'}</td>
          <td>{item.band || '—'}</td><td>{item.status}</td>
          <td><button type="button" className="text-button danger" disabled={busy} onClick={() => removeOne(item.job_id)} aria-label={`Delete search from ${friendlyDate(item.created_at)}`}>Delete</button></td>
        </tr>)}
      </tbody></table></div>
    </>}
    {user && <div className="history-actions">
      {confirm ? <div className="confirm-box" role="alertdialog" aria-label="Confirm">
        <span>{confirm === 'clear' ? 'Delete all your saved searches?' : 'Permanently delete your account and all saved searches?'}</span>
        <button type="button" className="secondary-button" onClick={() => setConfirm(null)}>Cancel</button>
        <button type="button" className="secondary-button danger-button" onClick={confirmed}>Yes, delete</button>
      </div> : <>
        {items && items.length > 0 && <button type="button" className="secondary-button" disabled={busy} onClick={() => setConfirm('clear')}>Clear history</button>}
        <button type="button" className="secondary-button" disabled={busy} onClick={() => setConfirm('account')}>Delete my account</button>
      </>}
    </div>}
    <SiteFooter compact /></main>;
}
