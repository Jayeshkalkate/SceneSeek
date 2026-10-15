'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from 'react';
import SiteFooter from '../components/SiteFooter';
import SiteHeader from '../components/SiteHeader';
import { useUser } from '../components/AuthButton';
import { CandidateCard, HitCard, confidenceLabel } from '../components/ResultCard';
import { apiFetch, formatBytes } from '../lib/api';
import type { PublicConfig, SearchHit } from '../lib/types';
import { useIdentify } from '../lib/useIdentify';

const ACCEPT = '.jpg,.jpeg,.png,.webp,.mp4,.webm,.mov';
const FALLBACK_CONFIG: PublicConfig = {
  google_login: false, google_client_id: '', require_login: false, max_image_mb: 10, max_video_mb: 25, max_video_seconds: 30, online_anime: true,
};

const isVideo = (file: File) => ['video/mp4', 'video/webm', 'video/quicktime'].includes(file.type) || /\.(mp4|webm|mov)$/i.test(file.name);

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [fileError, setFileError] = useState('');
  const [config, setConfig] = useState<PublicConfig>(FALLBACK_CONFIG);
  const [referenceStatus, setReferenceStatus] = useState<{ ready: boolean; titles: number; frames: number; algorithm: string } | null>(null);
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [waking, setWaking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLElement>(null);
  const { user, ready: authReady } = useUser();
  const { phase, job, error, elapsed, start, cancel, reset: resetIdentify } = useIdentify();
  const busy = phase === 'uploading' || phase === 'processing';
  const loginBlocked = config.require_login && authReady && !user;

  // Wake the (free-tier) API and load public config + index status.
  useEffect(() => {
    const wakeTimer = setTimeout(() => setWaking(true), 3000);
    const done = () => { clearTimeout(wakeTimer); setWaking(false); };
    apiFetch('/ping', { retries: 3 }).then(done, done);
    apiFetch<PublicConfig>('/v1/config').then(setConfig).catch(() => undefined);
    apiFetch<{ ready: boolean; titles: number; frames: number; algorithm: string }>('/v1/reference/status').then(setReferenceStatus).catch(() => setReferenceStatus(null));
    return () => clearTimeout(wakeTimer);
  }, []);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  useEffect(() => {
    if (phase === 'done') resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [phase]);

  const chooseFile = useCallback((next: File | null) => {
    resetIdentify();
    setFileError(''); setPreview(null); setFile(null);
    if (!next) return;
    const video = isVideo(next);
    if (!/\.(jpg|jpeg|png|webp|mp4|webm|mov)$/i.test(next.name)) { setFileError('Choose a JPG, PNG, WebP, MP4, WebM, or MOV file.'); return; }
    if (next.size === 0) { setFileError('That file is empty. Please choose another file.'); return; }
    const limit = (video ? config.max_video_mb : config.max_image_mb) * 1024 * 1024;
    if (next.size > limit) { setFileError(`That file is too large (${formatBytes(next.size)}). The limit is ${video ? config.max_video_mb : config.max_image_mb} MB for ${video ? 'video' : 'images'}.`); return; }
    setFile(next);
    if (!video) setPreview(URL.createObjectURL(next));
  }, [config.max_image_mb, config.max_video_mb, resetIdentify]);

  // Ctrl/Cmd+V pastes a screenshot straight from the clipboard.
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      if (busy) return;
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return;
      const item = Array.from(event.clipboardData?.items || []).find(entry => entry.type.startsWith('image/'));
      const pasted = item?.getAsFile();
      if (pasted) {
        event.preventDefault();
        const ext = pasted.type.split('/')[1] === 'jpeg' ? 'jpg' : pasted.type.split('/')[1] || 'png';
        chooseFile(new File([pasted], `pasted-screenshot.${ext}`, { type: pasted.type }));
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [busy, chooseFile]);

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => { chooseFile(event.target.files?.[0] || null); event.target.value = ''; };
  const onDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); if (!busy) chooseFile(event.dataTransfer.files?.[0] || null); };

  const runTextSearch = async () => {
    const q = query.trim();
    if (q.length < 2 || searching) return;
    setSearching(true); setSearchError(''); setHits(null);
    try {
      const data = await apiFetch<{ results: SearchHit[] }>(`/v1/search?q=${encodeURIComponent(q)}`);
      setHits(data.results || []);
    } catch (err) { setSearchError(err instanceof Error ? err.message : 'Search failed. Please try again.'); }
    finally { setSearching(false); }
  };

  const result = phase === 'done' ? job?.result : null;
  const shownError = fileError || (phase === 'failed' ? error : '');
  const queueAhead = job?.status === 'queued' ? job.queue_ahead : undefined;

  return (
    <main className="shell" id="main">
      <SiteHeader home />

      {waking && <div className="wake-banner" role="status"><span className="spinner" /> Waking the free server… this can take up to a minute after inactivity.</div>}

      <section className="hero" id="identify">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> ENTERTAINMENT, DECODED</div>
          <h1>You saw the scene.<br /><span>We’ll seek the source.</span></h1>
          <p className="hero-subtitle">Drop in a screenshot or a short clip. SceneSeek searches visual clues to help find the movie, series, or anime behind it.</p>
          <div className="hero-trust">
            <span><i className="check-icon">✓</i> Free to use</span>
            <span><i className="check-icon">✓</i> {config.require_login ? 'Google sign-in required' : 'No account needed'}</span>
            <span><i className="check-icon">✓</i> Uploads are temporary</span>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="art-glow" />
          <Image src="/sceneseek-logo.png" width={510} height={510} alt="" className="hero-logo" priority unoptimized />
          <span className="float-tag tag-top"><span className="tag-dot cyan" /> FRAME MATCH</span>
          <span className="float-tag tag-bottom"><span className="tag-dot purple" /> TITLE FOUND?</span>
        </div>
      </section>

      <section className="search-section" aria-labelledby="upload-title">
        <div className="section-heading">
          <span className="section-kicker">YOUR SCENE, YOUR CLUE</span>
          <h2 id="upload-title">Let’s find what you watched.</h2>
          <p>For best results, use a clear frame without heavy filters or large overlays. You can also paste a screenshot with <kbd>Ctrl</kbd> + <kbd>V</kbd>.</p>
        </div>
        <div
          className={`upload-panel ${dragging ? 'dragging' : ''}`}
          onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }}
          onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }}
          onDrop={onDrop}
        >
          <input ref={inputRef} className="visually-hidden" type="file" accept={ACCEPT} onChange={onInputChange} tabIndex={-1} aria-label="Choose a screenshot or short video" />
          {!file ? (
            <>
              <div className="upload-icon"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 31V8m0 0-9 9m9-9 9 9" /><path d="M9 29v10a2 2 0 0 0 2 2h26a2 2 0 0 0 2-2V29" /></svg></div>
              <h3>Drop your screenshot or clip here</h3>
              <p>or <button type="button" className="text-button" onClick={() => inputRef.current?.click()}>browse files</button> on your device</p>
              <div className="file-rules">
                <span>JPG · PNG · WEBP <b>≤ {config.max_image_mb} MB</b></span><span className="rule-divider" />
                <span>MP4 · WEBM · MOV <b>≤ {config.max_video_mb} MB / {config.max_video_seconds} sec</b></span>
              </div>
            </>
          ) : (
            <div className="selected-file">
              {preview ? <img className="selected-preview" src={preview} alt="Preview of selected upload" /> : <div className="video-preview"><span>▶</span><small>VIDEO CLIP</small></div>}
              <div className="selected-meta">
                <span className="selected-label">{busy ? 'ANALYZING' : 'READY TO ANALYZE'}</span>
                <strong>{file.name}</strong>
                <small>{formatBytes(file.size)} · {isVideo(file) ? 'Video clip' : 'Screenshot'}</small>
              </div>
              {!busy && <button type="button" className="remove-file" onClick={() => chooseFile(null)} aria-label="Remove selected file">×</button>}
            </div>
          )}
          {loginBlocked && <div className="error-message" role="alert">This site requires Google sign-in before identifying scenes. Use the sign-in button at the top of the page.</div>}
          {shownError && <div className="error-message" role="alert">{shownError}</div>}
          <div className="upload-actions">
            {busy ? (
              <>
                <button className="primary-button loading-button" type="button" disabled><span className="spinner" />{phase === 'uploading' ? 'Uploading securely…' : 'Searching visual clues…'}</button>
                <button type="button" className="text-button" onClick={cancel}>Cancel</button>
              </>
            ) : (
              <button className="primary-button" type="button" disabled={!file || loginBlocked} onClick={() => file && start(file)}>
                {phase === 'failed' ? 'Try again' : 'Identify this scene'} <span aria-hidden="true">↗</span>
              </button>
            )}
            <span className="privacy-note" title="Anime frames may be sent to trace.moe for matching">
              <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5" /><path d="M5 7V5a3 3 0 0 1 6 0v2" /></svg>
              Stored temporarily{config.online_anime ? ' · anime lookup uses trace.moe' : ''}
            </span>
          </div>
        </div>
      </section>

      {phase === 'processing' && (
        <section className="processing-card" aria-live="polite">
          <div className="processing-orb"><span /></div>
          <div>
            <strong>{queueAhead ? `In line — ${queueAhead} search${queueAhead === 1 ? '' : 'es'} ahead of yours` : 'Reading the scene'}</strong>
            <p>Extracting frames and comparing visual patterns. {elapsed > 20 ? 'Still working — a cold start or a longer clip can take a minute.' : 'This usually takes a few seconds.'} <span className="elapsed">{elapsed}s</span></p>
            <div className="progress-track"><div className="progress-bar" /></div>
          </div>
        </section>
      )}

      {result && (
        <section className="results-section" aria-live="polite" ref={resultsRef}>
          <div className="results-title">
            <div>
              <span className="section-kicker">SEARCH COMPLETE</span>
              <h2>{result.candidates.length ? 'These could be your scene.' : 'No strong match this time.'}</h2>
              <p>{result.message || (result.candidates.length ? 'Compare the candidates below. A low-confidence result means the visual evidence is ambiguous.' : 'Try a clearer screenshot, or search by title below.')}</p>
            </div>
            <button className="secondary-button" type="button" onClick={() => chooseFile(null)}>New search <span>＋</span></button>
          </div>
          {result.candidates.length > 0 && (
            <div className="match-summary">
              <div className={`confidence-mark confidence-${result.band}`}>
                <span className="confidence-ring">{result.band === 'high' ? '✓' : result.band === 'medium' ? '≈' : '?'}</span>
                <span><small>TOP MATCH</small><strong>{confidenceLabel(result.band)}</strong></span>
              </div>
              <div className="summary-metrics">
                <div><small>VISUAL METHOD</small><strong>{(result.visual_method || 'visual').toUpperCase()}</strong></div>
                <div><small>SEARCH TIME</small><strong>{(result.latency_ms / 1000).toFixed(1)}s</strong></div>
                <div><small>CANDIDATES</small><strong>{result.candidates.length}</strong></div>
              </div>
            </div>
          )}
          <div className="results-grid">{result.candidates.map((candidate, index) => <CandidateCard key={candidate.title_id} candidate={candidate} rank={index} jobId={job?.id} />)}</div>
          <p className="score-disclaimer">Match scores are ranking signals, not guaranteed probabilities. SceneSeek only searches titles in the current reference collection{config.online_anime ? ' plus online anime lookup' : ''}.</p>
        </section>
      )}

      <section className="search-section" aria-labelledby="text-title">
        <div className="section-heading">
          <span className="section-kicker">KNOW A TITLE OR A LINE?</span>
          <h2 id="text-title">Search by name instead.</h2>
          <p>Type a title, character or guess. Movies, series and anime are looked up from free public sources.</p>
        </div>
        <form className="text-search" onSubmit={event => { event.preventDefault(); runTextSearch(); }}>
          <input type="search" value={query} maxLength={120} onChange={event => setQuery(event.target.value)} placeholder="e.g. Inception, Breaking Bad, Your Name" aria-label="Search titles" />
          <button className="primary-button" type="submit" disabled={searching || query.trim().length < 2}>{searching ? 'Searching…' : 'Search'}</button>
        </form>
        {searchError && <div className="error-message" role="alert">{searchError}</div>}
        {hits && (hits.length === 0
          ? <p className="score-disclaimer">No titles found for “{query.trim()}”. Check the spelling or try fewer words.</p>
          : <div className="results-grid hits-grid">{hits.map(hit => <HitCard key={hit.title_id} hit={hit} />)}</div>)}
      </section>

      <section className="how-section" id="how-it-works">
        <div className="section-heading left-heading"><span className="section-kicker">NOT MAGIC. JUST SMART MATCHING.</span><h2>From a frame to a title.</h2><p>Three steps. No guessing what keyword you should have searched.</p></div>
        <div className="steps-grid">
          <article className="step-card"><div className="step-number">01</div><div className="step-icon step-icon-cyan">▧</div><h3>Share the scene</h3><p>Upload, drop or paste a screenshot or short clip from your device. No social-media scraping.</p></article>
          <article className="step-card"><div className="step-number">02</div><div className="step-icon step-icon-blue">⌘</div><h3>Compare the clues</h3><p>SceneSeek samples frames, removes near-duplicates, and compares them with its reference index.</p></article>
          <article className="step-card"><div className="step-number">03</div><div className="step-icon step-icon-pink">✧</div><h3>Explore the matches</h3><p>See ranked candidates with evidence and an uncertainty label when the match is ambiguous.</p></article>
        </div>
      </section>

      <section className="reference-note">
        <div className="reference-symbol">i</div>
        <div>
          <strong>{referenceStatus?.ready ? `Reference index ready · ${referenceStatus.titles} titles / ${referenceStatus.frames} frames` : 'The index makes identification possible.'}</strong>
          <p>{referenceStatus?.ready ? `This instance uses ${referenceStatus.algorithm} retrieval. Accuracy depends on the quality and coverage of its reference collection.` : 'This installation has no reference frames yet. Uploads and anime lookup work, but movie/series matches need a lawful reference collection. See the README for the index builder.'}</p>
        </div>
        <Link href="/stats">View evaluation ↗</Link>
      </section>

      <SiteFooter />
      
    </main>
  );
}
