'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import SiteFooter from '../../../components/SiteFooter';
import SiteHeader from '../../../components/SiteHeader';
import { apiFetch } from '../../../lib/api';
import type { TitleData } from '../../../lib/types';

export default function TitlePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ? decodeURIComponent(params.id) : '';
  const [title, setTitle] = useState<TitleData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [posterBroken, setPosterBroken] = useState(false);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    setLoading(true); setError(''); setTitle(null); setPosterBroken(false);
    apiFetch<TitleData>(`/v1/titles/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(setTitle)
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Title details could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id]);

  return <main className="shell subpage-shell" id="main"><SiteHeader />
    {loading ? <div className="subpage-state"><span className="spinner" /><p>Looking up title details…</p></div>
      : error ? <div className="subpage-state"><h1>We couldn’t load that title.</h1><p>{error}</p><Link href="/" className="primary-button link-button">Return home</Link></div>
      : title && <section className="detail-page">
        <div className="detail-poster">{title.poster_url && !posterBroken ? <img src={title.poster_url} alt={`Poster for ${title.title}`} referrerPolicy="no-referrer" onError={() => setPosterBroken(true)} /> : <div className="poster-placeholder detail-placeholder"><span>SS</span><small>SCENESEEK</small></div>}</div>
        <div className="detail-copy"><span className="section-kicker">TITLE DETAILS</span>
          <div className="detail-meta">{title.kind || 'Entertainment'}{title.year ? ` · ${title.year}` : ''}</div>
          <h1>{title.title}</h1>
          {title.original_title && title.original_title !== title.title && <p className="detail-original">{title.original_title}</p>}
          <div className="genre-row detail-genres">{(title.genres || []).map(genre => <span key={genre}>{genre}</span>)}</div>
          <h2>Synopsis</h2><p className="detail-synopsis">{title.synopsis || 'A synopsis has not been added to this reference entry yet.'}</p>
          {title.rating?.value !== null && title.rating?.value !== undefined && <div className="rating-row"><span className="rating-star">★</span><strong>{title.rating.value}</strong><small>{title.rating.source || 'Rating source not specified'}</small></div>}
          <div className="detail-disclosure"><strong>Source and attribution</strong><p>{title.provider || 'Reference collection'}{title.attribution ? ` · ${title.attribution}` : ''}</p></div>
          {title.external_url && <a href={title.external_url} target="_blank" rel="noreferrer" className="primary-button link-button">Open official info source ↗</a>}
          <p className="detail-disclaimer">This entry comes from SceneSeek’s reference index or a free public metadata source. External information and artwork remain subject to their original provider’s terms.</p>
        </div></section>}
    <SiteFooter compact /></main>;
}
