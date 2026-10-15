'use client';

import Link from 'next/link';
import { useState } from 'react';
import { apiFetch } from '../lib/api';
import type { Candidate, SearchHit } from '../lib/types';

export function confidenceLabel(value?: string) {
  return value === 'high' ? 'Strong lead' : value === 'medium' ? 'Possible match' : 'Low confidence';
}

function Poster({ url, title, rank }: { url?: string | null; title: string; rank?: number }) {
  const [broken, setBroken] = useState(false);
  return (
    <div className="poster-wrap">
      {url && !broken
        ? <img src={url} alt={`Poster for ${title}`} loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
        : <div className="poster-placeholder"><span>SS</span><small>SCENESEEK</small></div>}
      {rank !== undefined && <span className={`rank-badge ${rank === 0 ? 'rank-first' : ''}`}>#{rank + 1}</span>}
    </div>
  );
}

function timestamp(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}

export function CandidateCard({ candidate, rank, jobId }: { candidate: Candidate; rank: number; jobId?: string }) {
  const [verdict, setVerdict] = useState<'correct' | 'wrong' | null>(null);
  const [pending, setPending] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');

  const send = async (value: 'correct' | 'wrong') => {
    if (!jobId || pending) return;
    setPending(true); setFeedbackError('');
    try {
      await apiFetch('/v1/feedback', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, predicted_title_id: candidate.title_id, verdict: value }),
      });
      setVerdict(value);
    } catch (err) { setFeedbackError(err instanceof Error ? err.message : 'Could not save feedback.'); }
    finally { setPending(false); }
  };

  const where = [candidate.episode ? `Episode ${candidate.episode}` : '', candidate.timestamp_s != null ? `around ${timestamp(candidate.timestamp_s)}` : '']
    .filter(Boolean).join(' · ');

  return (
    <article className={`result-card ${rank === 0 ? 'top-result' : ''}`}>
      <Poster url={candidate.poster_url} title={candidate.title} rank={rank} />
      <div className="result-body">
        <div className="result-kicker">
          <span>{candidate.kind || 'Title'}</span>
          {candidate.year && <><span className="kicker-dot">·</span><span>{candidate.year}</span></>}
          <span className="kicker-spacer" />
          <span className={`confidence-pill pill-${candidate.confidence}`}>{confidenceLabel(candidate.confidence)}</span>
        </div>
        <h3>{candidate.title}</h3>
        {where && <p className="original-title">{where}</p>}
        {candidate.original_title && candidate.original_title !== candidate.title && <p className="original-title">{candidate.original_title}</p>}
        <div className="genre-row">{(candidate.genres || []).slice(0, 3).map(genre => <span key={genre}>{genre}</span>)}</div>
        <p className="result-synopsis">{candidate.synopsis || 'No synopsis was supplied in the current reference index.'}</p>
        <div className="score-strip" title="A ranking signal, not a probability">
          <span>Match score</span>
          <div className="score-track"><div className="score-fill" style={{ width: `${Math.max(0, Math.min(100, candidate.score * 100))}%` }} /></div>
          <strong>{Math.round(candidate.score * 100)}</strong>
        </div>
        <div className="result-links">
          <Link href={`/t/${encodeURIComponent(candidate.title_id)}`}>Details <span aria-hidden="true">↗</span></Link>
          {candidate.external_url && <a href={candidate.external_url} target="_blank" rel="noreferrer">Source ↗</a>}
        </div>
        {jobId && (
          <div className="feedback-row">
            {verdict ? <span className="feedback-thanks" role="status">Thanks — feedback saved.</span> : <>
              <span>Is this the one?</span>
              <button type="button" disabled={pending} onClick={() => send('correct')}>Yes</button>
              <button type="button" disabled={pending} onClick={() => send('wrong')}>No</button>
            </>}
          </div>
        )}
        {feedbackError && <p className="auth-error" role="alert">{feedbackError}</p>}
        {candidate.attribution && <p className="attribution">Source: {candidate.provider || 'reference collection'} · {candidate.attribution}</p>}
      </div>
    </article>
  );
}

export function HitCard({ hit }: { hit: SearchHit }) {
  return (
    <article className="result-card">
      <Poster url={hit.poster_url} title={hit.title} />
      <div className="result-body">
        <div className="result-kicker">
          <span>{hit.kind || 'Title'}</span>
          {hit.year && <><span className="kicker-dot">·</span><span>{hit.year}</span></>}
        </div>
        <h3>{hit.title}</h3>
        <div className="genre-row">{(hit.genres || []).slice(0, 3).map(g => <span key={g}>{g}</span>)}</div>
        <p className="result-synopsis">{hit.synopsis || 'No synopsis available.'}</p>
        <div className="result-links">
          <Link href={`/t/${encodeURIComponent(hit.title_id)}`}>Details <span aria-hidden="true">↗</span></Link>
          {hit.external_url && <a href={hit.external_url} target="_blank" rel="noreferrer">Open source ↗</a>}
        </div>
        <p className="attribution">Source: {hit.provider}</p>
      </div>
    </article>
  );
}
