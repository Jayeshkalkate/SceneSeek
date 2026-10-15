'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiFetch } from './api';
import type { JobState } from './types';

export type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'failed';
type Accepted = { job_id: string; status: string; poll_after_ms?: number };

const MAX_WAIT_MS = 5 * 60 * 1000;
const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));

/** Upload a file, then poll the job until it finishes. Cancel-safe and tolerant of brief network failures. */
export function useIdentify() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const run = useRef(0);
  const abort = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    run.current += 1;
    abort.current?.abort();
    setPhase('idle');
  }, []);

  useEffect(() => () => { run.current += 1; abort.current?.abort(); }, []);

  useEffect(() => {
    if (phase !== 'uploading' && phase !== 'processing') { setElapsed(0); return; }
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const start = useCallback(async (file: File) => {
    const id = ++run.current;
    const controller = new AbortController();
    abort.current = controller;
    const live = () => run.current === id;
    setError(''); setJob(null); setPhase('uploading');
    try {
      const form = new FormData();
      form.append('file', file);
      const accepted = await apiFetch<Accepted>('/v1/identify', { method: 'POST', body: form, timeoutMs: 180_000, signal: controller.signal });
      if (!live()) return;
      setPhase('processing');
      const began = Date.now();
      let failures = 0;
      while (live()) {
        if (Date.now() - began > MAX_WAIT_MS) throw new ApiError('This search is taking longer than expected. Please try again in a moment.');
        await sleep(Math.max(1000, accepted.poll_after_ms || 1500));
        if (!live()) return;
        let terminal: string | null = null;
        try {
          const state = await apiFetch<JobState>(`/v1/jobs/${encodeURIComponent(accepted.job_id)}`, { signal: controller.signal, retries: 0 });
          failures = 0;
          if (!live()) return;
          setJob(state);
          if (state.status === 'done') { setPhase('done'); return; }
          if (state.status === 'failed') terminal = state.error || 'The uploaded media could not be processed.';
        } catch (err) {
          if (!live()) return;
          // 404 = expired/unknown job, 4xx = hard failure; only network/5xx/429 blips are retried.
          const hard = err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 429;
          if (hard || ++failures > 6) throw err;
          if (err instanceof ApiError && err.retryAfter) await sleep(err.retryAfter * 1000);
        }
        if (terminal !== null) throw new ApiError(terminal);
      }
    } catch (err) {
      if (!live()) return;
      setPhase('failed');
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    }
  }, []);

  const reset = useCallback(() => {
    run.current += 1; abort.current?.abort();
    setPhase('idle'); setJob(null); setError('');
  }, []);

  return { phase, job, error, elapsed, start, cancel, reset, setError };
}
