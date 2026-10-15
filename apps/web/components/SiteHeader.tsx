import Image from 'next/image';
import Link from 'next/link';
import AuthButton from './AuthButton';

export default function SiteHeader({ home = false }: { home?: boolean }) {
  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label="SceneSeek home">
        <Image src="/sceneseek-logo.png" width={home ? 66 : 56} height={home ? 66 : 56} alt="" priority unoptimized />
        <span className="brand-word">Scene<span>Seek</span></span>
      </Link>
      <nav className="nav-links" aria-label="Main navigation">
        {home ? (
          <>
            <a href="#how-it-works">How it works</a>
            <Link href="/stats">Accuracy</Link>
            <AuthButton />
            <a className="nav-cta" href="#identify">Find a scene <span aria-hidden="true">↗</span></a>
          </>
        ) : (
          <>
            <AuthButton />
            <Link href="/" className="back-link">← Back to search</Link>
          </>
        )}
      </nav>
    </header>
  );
}
