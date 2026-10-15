import Link from 'next/link';

export default function SiteFooter({ compact = false }: { compact?: boolean }) {
  return (
    <footer className={`footer${compact ? ' compact-footer' : ''}`}>
      <Link href="/" className="footer-brand">
        <span className="brand-word">Scene<span>Seek</span></span>
        <small>SEE IT. SEEK IT. FIND IT.</small>
      </Link>
      <nav className="footer-links" aria-label="Footer">
        <Link href="/#how-it-works">How it works</Link>
        <Link href="/help">Help</Link>
        <Link href="/privacy">Privacy</Link>
        <Link href="/terms">Terms</Link>
        <Link href="/stats">Evaluation</Link>
        <a href="https://github.com/Jayeshkalkate/SceneSeek" target="_blank" rel="noreferrer">GitHub ↗</a>
      </nav>
      <p>Built to discover stories, not host them. © {new Date().getFullYear()} SceneSeek.</p>
    </footer>
  );
}
