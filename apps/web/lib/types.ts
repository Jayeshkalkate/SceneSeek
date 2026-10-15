export type Band = 'high' | 'medium' | 'low' | 'none';
export type Rating = { value?: string | number | null; source?: string | null };

export type Candidate = {
  title_id: string; title: string; original_title?: string | null; kind?: string; year?: number | null;
  synopsis?: string | null; genres?: string[]; poster_url?: string | null; rating?: Rating;
  external_url?: string | null; provider?: string | null; attribution?: string | null;
  score: number; confidence: 'high' | 'medium' | 'low';
  evidence?: { visual?: number; text?: number; audio?: number };
  episode?: number | string | null; timestamp_s?: number | null; preview_url?: string | null;
};

export type SearchHit = {
  title_id: string; title: string; kind?: string; year?: number | null; synopsis?: string | null;
  genres?: string[]; poster_url?: string | null; external_url?: string | null; provider?: string;
};

export type IdentifyResult = {
  band: Band; margin: number; candidates: Candidate[]; signals_used: string[]; latency_ms: number;
  visual_method?: string | null; message?: string | null; scene_caption?: string | null;
};

export type JobState = {
  id: string; status: 'queued' | 'processing' | 'done' | 'failed'; progress: number;
  result?: IdentifyResult | null; error?: string | null; queue_ahead?: number; attempts?: number;
};

export type PublicConfig = {
  google_login: boolean; google_client_id: string; require_login: boolean;
  max_image_mb: number; max_video_mb: number; max_video_seconds: number; online_anime: boolean;
};

export type TitleData = {
  title_id?: string; title: string; original_title?: string | null; kind?: string; year?: number | null;
  synopsis?: string | null; genres?: string[]; poster_url?: string | null; rating?: Rating;
  external_url?: string | null; provider?: string; attribution?: string;
};

export type HistoryItem = {
  job_id: string; status: string; created_at: string; title?: string | null; title_id?: string | null; band?: string | null;
};

export type User = { id: string; email: string; name?: string | null; picture?: string | null };
