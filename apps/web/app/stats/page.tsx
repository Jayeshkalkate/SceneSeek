'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import SiteFooter from '../../components/SiteFooter';
import SiteHeader from '../../components/SiteHeader';
import { apiFetch } from '../../lib/api';

type Stats = {
  evaluation_available: boolean;
  evaluation?: { n?: number; top1?: number; top5?: number; mrr?: number; p50_ms?: number; p95_ms?: number; high_band_precision?: number | null; per_title?: Record<string, { title?: string; n?: number; top1?: number }> } | null;
  feedback_count: number; feedback_verdicts: Record<string, number>; disclaimer: string;
};
const pct = (value?: number | null) => (value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`);

export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Stats>('/v1/stats/accuracy', { signal: controller.signal }).then(setStats)
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load metrics.'); });
    return () => controller.abort();
  }, []);
  const evaluation = stats?.evaluation;
  return <main className="shell subpage-shell" id="main"><SiteHeader />
    <section className="stats-hero"><span className="section-kicker">MEASURE WHAT MATTERS</span><h1>Accuracy, without the hype.</h1><p>SceneSeek reports results from a labeled evaluation set when one has been run. Feedback volume is shown separately; it is not a substitute for a controlled accuracy test.</p></section>
    {error && <div className="error-message stats-error" role="alert">{error}</div>}
    {!stats && !error && <div className="subpage-state"><span className="spinner" /><p>Loading evaluation metrics…</p></div>}
    {stats && <><div className="stats-status"><span className={`status-dot ${stats.evaluation_available ? 'status-ready' : ''}`} /><strong>{stats.evaluation_available ? 'Labeled evaluation report available' : 'Evaluation report not yet generated'}</strong></div>
      {evaluation ? <><div className="stats-grid">
        <article className="stat-card"><small>TOP-1 ACCURACY</small><strong>{pct(evaluation.top1)}</strong><p>Correct title ranked first</p></article>
        <article className="stat-card"><small>TOP-5 ACCURACY</small><strong>{pct(evaluation.top5)}</strong><p>Correct title in first five</p></article>
        <article className="stat-card"><small>MEAN RECIPROCAL RANK</small><strong>{evaluation.mrr === undefined ? '—' : evaluation.mrr.toFixed(3)}</strong><p>Rewards correct higher ranks</p></article>
        <article className="stat-card"><small>HIGH-BAND PRECISION</small><strong>{pct(evaluation.high_band_precision)}</strong><p>Only meaningful when calibrated</p></article></div>
        <div className="latency-panel"><div><small>P50 LATENCY</small><strong>{evaluation.p50_ms === undefined ? '—' : `${evaluation.p50_ms} ms`}</strong></div><div><small>P95 LATENCY</small><strong>{evaluation.p95_ms === undefined ? '—' : `${evaluation.p95_ms} ms`}</strong></div><p>Latency values should include preprocessing, embedding and retrieval for each labeled sample.</p></div>
        {evaluation.per_title && <section className="per-title-panel"><h2>Performance by title</h2><div className="table-scroll"><table><thead><tr><th>Title</th><th>Samples</th><th>Top-1</th></tr></thead><tbody>{Object.entries<{ title?: string; n?: number; top1?: number }>(evaluation.per_title).map(([key, value]) => <tr key={key}><td>{value.title || key}</td><td>{value.n ?? '—'}</td><td>{pct(value.top1)}</td></tr>)}</tbody></table></div></section>}</>
        : <div className="empty-evaluation"><div className="empty-chart" aria-hidden="true"><span /><span /><span /><span /><span /><span /></div><h2>No accuracy claims yet.</h2><p>Add held-out labeled samples to <code>tests/fixtures/labels.json</code>, run <code>python tools/evaluate.py</code>, and save the generated report. This page will display the measured metrics automatically.</p><Link href="/" className="primary-button link-button">Try a scene ↗</Link></div>}
      <div className="feedback-stats"><div><span className="section-kicker">COMMUNITY CORRECTIONS</span><h2>Feedback received</h2><p>Feedback is useful for discovering failure cases, but it may be self-selected and does not represent test-set accuracy.</p></div><div className="feedback-count"><strong>{stats.feedback_count}</strong><span>reports</span><div className="verdicts">{Object.entries(stats.feedback_verdicts || {}).map(([key, value]) => <span key={key}>{key}: <b>{value}</b></span>)}</div></div></div><p className="stats-disclaimer">{stats.disclaimer}</p></>}
    <SiteFooter compact /></main>;
}
