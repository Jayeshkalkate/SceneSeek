'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from 'react';

const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const IMAGE_MAX = 10 * 1024 * 1024;
const VIDEO_MAX = 25 * 1024 * 1024;
const ACCEPT = '.jpg,.jpeg,.png,.webp,.mp4,.webm,.mov';

type Candidate = {
  title_id: string; title: string; original_title?: string | null; kind?: string; year?: number | null;
  synopsis?: string | null; genres?: string[]; poster_url?: string | null;
  rating?: { value?: string | number | null; source?: string | null }; external_url?: string | null;
  provider?: string | null; attribution?: string | null; score: number; confidence: 'high' | 'medium' | 'low';
  evidence?: { visual?: number; text?: number; audio?: number };
  episode?: number | string | null; timestamp_s?: number | null; preview_url?: string | null;
};
type SearchHit = { title_id: string; title: string; kind?: string; year?: number | null; synopsis?: string | null; genres?: string[]; poster_url?: string | null; external_url?: string | null; provider?: string };
type Result = {
  band: 'high' | 'medium' | 'low' | 'none'; margin: number; candidates: Candidate[];
  signals_used: string[]; latency_ms: number; visual_method?: string | null; message?: string | null;
  scene_caption?: string | null;
};
type Job = { job_id: string; status: string; poll_after_ms?: number };
type JobState = { id: string; status: string; progress: number; result?: Result | null; error?: string | null };

function sizeLabel(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function isVideo(file: File) { return ['video/mp4', 'video/webm', 'video/quicktime'].includes(file.type) || /\.(mp4|webm|mov)$/i.test(file.name); }
function confidenceLabel(value?: string) { return value === 'high' ? 'Strong lead' : value === 'medium' ? 'Possible match' : 'Low confidence'; }

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'failed'>('idle');
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState('');
  const [referenceStatus, setReferenceStatus] = useState<{ ready: boolean; titles: number; frames: number; algorithm: string } | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelRef = useRef(false);

  useEffect(() => {
    fetch(`${API}/v1/reference/status`).then(r => r.ok ? r.json() : null).then(data => data && setReferenceStatus(data)).catch(() => setReferenceStatus(null));
    return () => { cancelRef.current = true; };
  }, []);

  const chooseFile = useCallback((next: File | null) => {
    setError(''); setJob(null); setPhase('idle'); setFeedbackSent({});
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null); setFile(null);
    if (!next) return;
    const video = isVideo(next);
    const allowed = /\.(jpg|jpeg|png|webp|mp4|webm|mov)$/i.test(next.name);
    if (!allowed) { setError('Choose a JPG, PNG, WebP, MP4, WebM, or MOV file.'); return; }
    const limit = video ? VIDEO_MAX : IMAGE_MAX;
    if (next.size > limit) { setError(`That file is too large. The limit is ${video ? '25 MB for video' : '10 MB for images'}.`); return; }
    if (next.size === 0) { setError('That file is empty. Please choose another file.'); return; }
    setFile(next);
    if (!video) setPreview(URL.createObjectURL(next));
  }, [preview]);

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0] || null);
  const onDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0] || null); };

  const startSearch = async () => {
    if (!file || phase === 'uploading' || phase === 'processing') return;
    cancelRef.current = false; setError(''); setPhase('uploading'); setJob(null);
    try {
      const form = new FormData(); form.append('file', file);
      const response = await fetch(`${API}/v1/identify`, { method: 'POST', body: form });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Could not upload the file. Please retry.');
      const accepted = payload as Job;
      setPhase('processing');
      const started = Date.now();
      while (!cancelRef.current) {
        if (Date.now() - started > 4 * 60 * 1000) throw new Error('This search is taking longer than expected. Check the API and worker, then retry.');
        await new Promise(resolve => setTimeout(resolve, Math.max(1000, accepted.poll_after_ms || 1500)));
        const poll = await fetch(`${API}/v1/jobs/${encodeURIComponent(accepted.job_id)}`, { cache: 'no-store' });
        const state = await poll.json().catch(() => ({}));
        if (!poll.ok) throw new Error(state.detail || 'The search status could not be retrieved.');
        setJob(state as JobState);
        if (state.status === 'done') { setPhase('done'); return; }
        if (state.status === 'failed') { throw new Error(state.error || 'The uploaded media could not be processed.'); }
      }
    } catch (err) {
      setPhase('failed'); setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    }
  };

  const sendFeedback = async (candidate: Candidate, verdict: 'correct' | 'wrong') => {
    if (!job?.id) return;
    try {
      const response = await fetch(`${API}/v1/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: job.id, predicted_title_id: candidate.title_id, verdict }) });
      if (!response.ok) throw new Error('Feedback could not be saved.');
      setFeedbackSent(prev => ({ ...prev, [candidate.title_id]: verdict }));
    } catch { setError('Could not save your feedback right now. Please try again.'); }
  };

  const runTextSearch = async () => {
    const q = query.trim();
    if (q.length < 2 || searching) return;
    setSearching(true); setSearchError(''); setHits(null);
    try {
      const response = await fetch(`${API}/v1/search?q=${encodeURIComponent(q)}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Search failed. Please try again.');
      setHits((data.results || []) as SearchHit[]);
    } catch (err) { setSearchError(err instanceof Error ? err.message : 'Search failed. Please try again.'); }
    finally { setSearching(false); }
  };

  const reset = () => { cancelRef.current = true; chooseFile(null); setJob(null); setError(''); setPhase('idle'); };

  return (
    <main className="shell">
      <header className="topbar">
        <Link href="/" className="brand" aria-label="SceneSeek home">
          <Image src="/sceneseek-logo.png" width={66} height={66} alt="" priority unoptimized />
          <span className="brand-word">Scene<span>Seek</span></span>
        </Link>
        <nav className="nav-links" aria-label="Main navigation">
          <a href="#how-it-works">How it works</a><Link href="/stats">Accuracy</Link>
          <a className="nav-cta" href="#identify">Find a scene <span aria-hidden="true">↗</span></a>
        </nav>
      </header>

      <section className="hero" id="identify">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> ENTERTAINMENT, DECODED</div>
          <h1>You saw the scene.<br /><span>We’ll seek the source.</span></h1>
          <p className="hero-subtitle">Drop in a screenshot or a short clip. SceneSeek searches visual clues to help find the movie, series, or anime behind it.</p>
          <div className="hero-trust">
            <span><i className="check-icon">✓</i> Free to use</span>
            <span><i className="check-icon">✓</i> No account needed</span>
            <span><i className="check-icon">✓</i> Uploads are temporary</span>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" />
          <div className="art-glow" />
          <Image src="/sceneseek-logo.png" width={510} height={510} alt="" className="hero-logo" priority unoptimized />
          <span className="float-tag tag-top"><span className="tag-dot cyan" /> FRAME MATCH</span>
          <span className="float-tag tag-bottom"><span className="tag-dot purple" /> TITLE FOUND?</span>
        </div>
      </section>

      <section className="search-section" aria-labelledby="upload-title">
        <div className="section-heading">
          <span className="section-kicker">YOUR SCENE, YOUR CLUE</span>
          <h2 id="upload-title">Let’s find what you watched.</h2>
          <p>For best results, use a clear frame without heavy filters or large overlays.</p>
        </div>
        <div className={`upload-panel ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }} onDrop={onDrop}>
          <input ref={inputRef} className="visually-hidden" type="file" accept={ACCEPT} onChange={onInputChange} aria-label="Choose a screenshot or short video" />
          {!file ? (
            <>
              <div className="upload-icon"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 31V8m0 0-9 9m9-9 9 9" /><path d="M9 29v10a2 2 0 0 0 2 2h26a2 2 0 0 0 2-2V29" /></svg></div>
              <h3>Drop your screenshot or clip here</h3>
              <p>or <button type="button" className="text-button" onClick={() => inputRef.current?.click()}>browse files</button> on your device</p>
              <div className="file-rules"><span>JPG · PNG · WEBP <b>≤ 10 MB</b></span><span className="rule-divider" /><span>MP4 · WEBM · MOV <b>≤ 25 MB / 30 sec</b></span></div>
            </>
          ) : (
            <div className="selected-file">
              {preview ? <img className="selected-preview" src={preview} alt="Preview of selected upload" /> : <div className="video-preview"><span>▶</span><small>VIDEO CLIP</small></div>}
              <div className="selected-meta"><span className="selected-label">READY TO ANALYZE</span><strong>{file.name}</strong><small>{sizeLabel(file.size)} · {isVideo(file) ? 'Video clip' : 'Screenshot'}</small></div>
              <button type="button" className="remove-file" onClick={reset} aria-label="Remove selected file">×</button>
            </div>
          )}
          {error && <div className="error-message" role="alert">{error}</div>}
          <div className="upload-actions">
            {phase === 'uploading' || phase === 'processing' ? (
              <button className="primary-button loading-button" type="button" disabled><span className="spinner" />{phase === 'uploading' ? 'Uploading securely…' : 'Searching visual clues…'}</button>
            ) : (
              <button className="primary-button" type="button" disabled={!file} onClick={startSearch}>Identify this scene <span aria-hidden="true">↗</span></button>
            )}
            <span className="privacy-note" title="Anime frames may be sent to trace.moe for matching"><svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5 7V5a3 3 0 0 1 6 0v2"/></svg> Stored temporarily · anime lookup uses trace.moe</span>
          </div>
        </div>
      </section>

      {phase === 'processing' && <section className="processing-card" aria-live="polite"><div className="processing-orb"><span /></div><div><strong>Reading the scene</strong><p>Extracting frames and comparing visual patterns in the reference collection. This can take a little longer during a cold start.</p><div className="progress-track"><div className="progress-bar" /></div></div></section>}

      {phase === 'done' && job?.result && <section className="results-section" aria-live="polite">
        <div className="results-title"><div><span className="section-kicker">SEARCH COMPLETE</span><h2>{job.result.candidates.length ? 'These could be your scene.' : 'No strong match this time.'}</h2><p>{job.result.message || (job.result.candidates.length ? 'Compare the candidates below. A low-confidence result means the visual evidence is ambiguous.' : 'Try a clearer screenshot or add more titles to the reference collection.')}</p></div><button className="secondary-button" type="button" onClick={reset}>New search <span>＋</span></button></div>
        {job.result.candidates.length > 0 && <div className="match-summary"><div className={`confidence-mark confidence-${job.result.band}`}><span className="confidence-ring">{job.result.band === 'high' ? '✓' : job.result.band === 'medium' ? '≈' : '?'}</span><span><small>TOP MATCH</small><strong>{confidenceLabel(job.result.band)}</strong></span></div><div className="summary-metrics"><div><small>VISUAL METHOD</small><strong>{(job.result.visual_method || 'visual').toUpperCase()}</strong></div><div><small>SEARCH TIME</small><strong>{(job.result.latency_ms / 1000).toFixed(1)}s</strong></div><div><small>CANDIDATES</small><strong>{job.result.candidates.length}</strong></div></div></div>}
        <div className="results-grid">{job.result.candidates.map((candidate, index) => <article className={`result-card ${index === 0 ? 'top-result' : ''}`} key={candidate.title_id}>
          <div className="poster-wrap">{candidate.poster_url ? <img src={candidate.poster_url} alt={`Poster for ${candidate.title}`} loading="lazy" referrerPolicy="no-referrer" onError={event => { event.currentTarget.style.display = 'none'; }} /> : <div className="poster-placeholder"><span>SS</span><small>SCENESEEK</small></div>}<span className={`rank-badge ${index === 0 ? 'rank-first' : ''}`}>#{index + 1}</span></div>
          <div className="result-body"><div className="result-kicker"><span>{candidate.kind || 'Title'}</span>{candidate.year && <><span className="kicker-dot">·</span><span>{candidate.year}</span></>}<span className="kicker-spacer" /><span className={`confidence-pill pill-${candidate.confidence}`}>{confidenceLabel(candidate.confidence)}</span></div><h3>{candidate.title}</h3>{(candidate.episode || candidate.timestamp_s != null) && <p className="original-title">{candidate.episode ? `Episode ${candidate.episode}` : ''}{candidate.episode && candidate.timestamp_s != null ? ' · ' : ''}{candidate.timestamp_s != null ? `around ${Math.floor(candidate.timestamp_s / 60)}:${String(Math.floor(candidate.timestamp_s % 60)).padStart(2, '0')}` : ''}</p>}{candidate.original_title && candidate.original_title !== candidate.title && <p className="original-title">{candidate.original_title}</p>}<div className="genre-row">{(candidate.genres || []).slice(0, 3).map(genre => <span key={genre}>{genre}</span>)}</div><p className="result-synopsis">{candidate.synopsis || 'No synopsis was supplied in the current reference index.'}</p><div className="score-strip"><span>Match score</span><div className="score-track"><div className="score-fill" style={{ width: `${Math.max(0, Math.min(100, candidate.score * 100))}%` }} /></div><strong>{Math.round(candidate.score * 100)}</strong></div><div className="result-links"><Link href={`/t/${encodeURIComponent(candidate.title_id)}`}>Details <span>↗</span></Link>{candidate.external_url && <a href={candidate.external_url} target="_blank" rel="noreferrer">Source ↗</a>}</div><div className="feedback-row">{feedbackSent[candidate.title_id] ? <span className="feedback-thanks">Thanks — feedback saved.</span> : <><span>Is this the one?</span><button type="button" onClick={() => sendFeedback(candidate, 'correct')}>Yes</button><button type="button" onClick={() => sendFeedback(candidate, 'wrong')}>No</button></>}</div>{candidate.attribution && <p className="attribution">Source: {candidate.provider || 'reference collection'} · {candidate.attribution}</p>}</div>
        </article>)}</div>
        <p className="score-disclaimer">Match scores are ranking signals, not guaranteed probabilities. SceneSeek only searches titles in the current reference collection.</p>
      </section>}

      <section className="search-section" aria-labelledby="text-title">
        <div className="section-heading"><span className="section-kicker">KNOW A TITLE OR A LINE?</span><h2 id="text-title">Search by name instead.</h2><p>Type a title, character or guess. Movies, series and anime are looked up from free public sources.</p></div>
        <form className="text-search" onSubmit={event => { event.preventDefault(); runTextSearch(); }}>
          <input type="search" value={query} maxLength={120} onChange={event => setQuery(event.target.value)} placeholder="e.g. Inception, Breaking Bad, Your Name" aria-label="Search titles" />
          <button className="primary-button" type="submit" disabled={searching || query.trim().length < 2}>{searching ? 'Searching…' : 'Search'}</button>
        </form>
        {searchError && <div className="error-message" role="alert">{searchError}</div>}
        {hits && <div className="results-grid hits-grid">{hits.length === 0 ? <p className="score-disclaimer">No titles found.</p> : hits.map(hit => <article className="result-card" key={hit.title_id}><div className="poster-wrap">{hit.poster_url ? <img src={hit.poster_url} alt={`Poster for ${hit.title}`} loading="lazy" referrerPolicy="no-referrer" /> : <div className="poster-placeholder"><span>SS</span><small>SCENESEEK</small></div>}</div><div className="result-body"><div className="result-kicker"><span>{hit.kind || 'Title'}</span>{hit.year && <><span className="kicker-dot">·</span><span>{hit.year}</span></>}</div><h3>{hit.title}</h3><div className="genre-row">{(hit.genres || []).slice(0, 3).map(g => <span key={g}>{g}</span>)}</div><p className="result-synopsis">{hit.synopsis || 'No synopsis available.'}</p>{hit.external_url && <div className="result-links"><a href={hit.external_url} target="_blank" rel="noreferrer">Open source ↗</a></div>}<p className="attribution">Source: {hit.provider}</p></div></article>)}</div>}
      </section>

      <section className="how-section" id="how-it-works"><div className="section-heading left-heading"><span className="section-kicker">NOT MAGIC. JUST SMART MATCHING.</span><h2>From a frame to a title.</h2><p>Three steps. No guessing what keyword you should have searched.</p></div><div className="steps-grid"><article className="step-card"><div className="step-number">01</div><div className="step-icon step-icon-cyan">▧</div><h3>Share the scene</h3><p>Upload a screenshot or a short clip directly from your device. No social-media scraping.</p></article><article className="step-card"><div className="step-number">02</div><div className="step-icon step-icon-blue">⌘</div><h3>Compare the clues</h3><p>SceneSeek samples frames, removes near-duplicates, and compares them with its reference index.</p></article><article className="step-card"><div className="step-number">03</div><div className="step-icon step-icon-pink">✧</div><h3>Explore the matches</h3><p>See ranked candidates with evidence and an uncertainty label when the match is ambiguous.</p></article></div></section>

      <section className="reference-note"><div className="reference-symbol">i</div><div><strong>{referenceStatus?.ready ? `Reference index ready · ${referenceStatus.titles} titles / ${referenceStatus.frames} frames` : 'The index makes identification possible.'}</strong><p>{referenceStatus?.ready ? `This instance uses ${referenceStatus.algorithm} retrieval. Accuracy depends on the quality and coverage of its reference collection.` : 'This installation does not have reference frames yet. The website and upload pipeline work, but meaningful title matches require a lawful reference collection. See the project README for the index builder.'}</p></div><Link href="/stats">View evaluation ↗</Link></section>

      <footer className="footer"><Link href="/" className="footer-brand"><span className="brand-word">Scene<span>Seek</span></span><small>SEE IT. SEEK IT. FIND IT.</small></Link><div className="footer-links"><a href="#how-it-works">How it works</a><Link href="/stats">Accuracy</Link><a href="https://github.com/" target="_blank" rel="noreferrer">Open-source ready</a></div><p>Built to discover stories, not host them. © {new Date().getFullYear()} SceneSeek.</p></footer>
    </main>
  );
}
