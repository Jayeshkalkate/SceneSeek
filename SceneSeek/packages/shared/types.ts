export type ConfidenceBand = 'high' | 'medium' | 'low' | 'none';
export type MediaKind = 'image' | 'video';
export type JobStatus = 'queued' | 'processing' | 'done' | 'failed';

export interface Candidate {
  title_id: string;
  title: string;
  original_title?: string | null;
  kind: 'anime' | 'movie' | 'series' | 'unknown';
  year?: number | null;
  synopsis?: string | null;
  genres: string[];
  poster_url?: string | null;
  rating: { value?: string | number | null; source?: string | null };
  external_url?: string | null;
  provider?: string | null;
  attribution?: string | null;
  score: number;
  confidence: Exclude<ConfidenceBand, 'none'>;
  evidence: { visual?: number; text?: number; audio?: number };
}

export interface IdentificationResult {
  band: ConfidenceBand;
  margin: number;
  scene_caption?: string | null;
  candidates: Candidate[];
  signals_used: string[];
  latency_ms: number;
  visual_method?: string | null;
  message?: string | null;
}

export interface JobStatusResponse {
  id: string;
  status: JobStatus;
  progress: number;
  result?: IdentificationResult | null;
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
}
