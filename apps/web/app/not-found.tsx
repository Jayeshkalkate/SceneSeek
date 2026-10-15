import Link from 'next/link';
import SiteFooter from '../components/SiteFooter';
import SiteHeader from '../components/SiteHeader';

export const metadata = { title: 'Page not found — SceneSeek' };

export default function NotFound() {
  return (
    <main className="shell subpage-shell" id="main">
      <SiteHeader />
      <div className="subpage-state">
        <span className="section-kicker">ERROR 404</span>
        <h1>This scene is missing.</h1>
        <p>The page you’re looking for doesn’t exist or has moved.</p>
        <Link href="/" className="primary-button link-button">Return home</Link>
      </div>
      <SiteFooter compact />
    </main>
  );
}
