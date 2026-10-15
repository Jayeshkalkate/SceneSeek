'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
type TitleData = {
  title_id?: string; title: string; original_title?: string | null; kind?: string; year?: number | null;
  synopsis?: string | null; genres?: string[]; poster_url?: string | null;
  rating?: { value?: string | number | null; source?: string | null }; external_url?: string | null;
  provider?: string; attribution?: string;
};

export default function TitlePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [title, setTitle] = useState<TitleData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    fetch(`${API}/v1/titles/${encodeURIComponent(id)}`, { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Title details could not be loaded.');
        return data as TitleData;
      })
      .then(setTitle)
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Title details could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id]);

  return <main className="shell subpage-shell"><header className="topbar"><Link href="/" className="brand"><Image src="/sceneseek-logo.png" width={56} height={56} alt="" unoptimized /><span className="brand-word">Scene<span>Seek</span></span></Link><Link href="/" className="back-link">← Back to search</Link></header>
    {loading ? <div className="subpage-state"><span className="spinner" /><p>Looking up title details…</p></div> : error ? <div className="subpage-state"><h1>We couldn’t load that title.</h1><p>{error}</p><Link href="/" className="primary-button link-button">Return home</Link></div> : title && <section className="detail-page"><div className="detail-poster">{title.poster_url ? <img src={title.poster_url} alt={`Poster for ${title.title}`} referrerPolicy="no-referrer" /> : <div className="poster-placeholder detail-placeholder"><span>SS</span><small>SCENESEEK</small></div>}</div><div className="detail-copy"><span className="section-kicker">TITLE DETAILS</span><div className="detail-meta">{title.kind || 'Entertainment'}{title.year ? ` · ${title.year}` : ''}</div><h1>{title.title}</h1>{title.original_title && title.original_title !== title.title && <p className="detail-original">{title.original_title}</p>}<div className="genre-row detail-genres">{(title.genres || []).map(genre => <span key={genre}>{genre}</span>)}</div><h2>Synopsis</h2><p className="detail-synopsis">{title.synopsis || 'A synopsis has not been added to this reference entry yet.'}</p>{title.rating?.value !== null && title.rating?.value !== undefined && <div className="rating-row"><span className="rating-star">★</span><strong>{title.rating.value}</strong><small>{title.rating.source || 'Rating source not specified'}</small></div>}<div className="detail-disclosure"><strong>Source and attribution</strong><p>{title.provider || 'Reference collection'}{title.attribution ? ` · ${title.attribution}` : ''}</p></div>{title.external_url && <a href={title.external_url} target="_blank" rel="noreferrer" className="primary-button link-button">Open official info source ↗</a>}<p className="detail-disclaimer">This entry is part of SceneSeek’s reference index. External information and artwork remain subject to their original provider’s terms.</p></div></section>}
    <footer className="footer compact-footer"><Link href="/" className="footer-brand"><span className="brand-word">Scene<span>Seek</span></span><small>SEE IT. SEEK IT. FIND IT.</small></Link><Link href="/stats">Evaluation dashboard ↗</Link><p>SceneSeek · Free-tier-first entertainment search.</p></footer>
  </main>;
}
