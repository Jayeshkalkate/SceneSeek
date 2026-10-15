-- SceneSeek v1 schema. Run in a Supabase SQL editor or with the Supabase CLI.
-- Reference vectors are stored in pgvector only when USE_PGVECTOR=true.
create extension if not exists vector;
create extension if not exists pg_trgm;
create extension if not exists pgcrypto;

create table if not exists jobs (
  id text primary key,
  status text not null default 'queued' check (status in ('queued','processing','done','failed')),
  input_kind text not null check (input_kind in ('image','video')),
  input_path text,
  mime varchar(120) not null,
  bytes integer not null check (bytes > 0),
  sha256 varchar(64) not null,
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  error text,
  result jsonb,
  latency_ms integer,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create index if not exists ix_jobs_status_created on jobs(status, created_at);
create index if not exists ix_jobs_sha256 on jobs(sha256);

create table if not exists feedback (
  id bigserial primary key,
  job_id text references jobs(id) on delete set null,
  predicted_title_id text,
  correct_title_id text,
  verdict text not null check (verdict in ('correct','wrong','unknown')),
  note text,
  created_at timestamptz not null default now()
);
create index if not exists ix_feedback_created on feedback(created_at);

create table if not exists takedown_requests (
  id bigserial primary key,
  source_url text not null,
  reason text not null,
  contact_email varchar(320),
  status varchar(16) not null default 'open',
  created_at timestamptz not null default now()
);

-- A compact title catalogue mirrors metadata in index.json and powers vector search.
create table if not exists titles (
  id text primary key,
  title text not null,
  original_title text,
  kind text not null check (kind in ('anime','movie','series','unknown')),
  year integer,
  synopsis text,
  poster_url text,
  genres jsonb not null default '[]'::jsonb,
  rating_value text,
  rating_source text,
  external_url text,
  provider text,
  attribution text,
  raw jsonb,
  fetched_at timestamptz not null default now()
);
create index if not exists ix_titles_title_trgm on titles using gin (title gin_trgm_ops);
create index if not exists ix_titles_kind on titles(kind);

create table if not exists ref_frames (
  id bigserial primary key,
  title_id text not null references titles(id) on delete cascade,
  frame_path text not null,
  embedding vector(512) not null,
  dhash bit(64),
  created_at timestamptz not null default now()
);
create index if not exists ix_ref_frames_title on ref_frames(title_id);
-- HNSW keeps nearest-neighbour retrieval responsive for moderate reference collections.
create index if not exists ix_ref_frames_embedding_hnsw on ref_frames
  using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);

create table if not exists ref_texts (
  id bigserial primary key,
  title_id text not null references titles(id) on delete cascade,
  kind text not null check (kind in ('subtitle','synopsis','ocr')),
  content text not null,
  tsv tsvector generated always as (to_tsvector('simple', coalesce(content,''))) stored
);
create index if not exists ix_ref_texts_tsv on ref_texts using gin(tsv);
create index if not exists ix_ref_texts_title on ref_texts(title_id);

create or replace function purge_old_jobs() returns void language sql as $$
  update jobs set input_path = null
   where created_at < now() - interval '24 hours' and input_path is not null;
$$;


create table if not exists metadata_cache (
  title_id text primary key,
  data jsonb not null,
  fetched_at timestamptz not null default now()
);

-- No anonymous/public policies are created. Public clients must call the API;
-- server-side connections use private credentials. Keep service-role keys secret.
alter table jobs enable row level security;
alter table feedback enable row level security;
alter table takedown_requests enable row level security;
alter table titles enable row level security;
alter table ref_frames enable row level security;
alter table ref_texts enable row level security;
alter table metadata_cache enable row level security;
