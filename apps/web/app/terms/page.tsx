import Image from 'next/image';
import Link from 'next/link';

export const metadata = { title: 'Terms — SceneSeek', description: 'Usage guidelines for SceneSeek.' };

export default function TermsPage() {
  return <main className="shell subpage-shell legal-page">
    <header className="topbar"><Link href="/" className="brand"><Image src="/sceneseek-logo.png" width={56} height={56} alt="" unoptimized /><span className="brand-word">Scene<span>Seek</span></span></Link><Link href="/" className="back-link">← Back to search</Link></header>
    <section className="stats-hero"><span className="section-kicker">TERMS OF USE</span><h1>Use SceneSeek responsibly.</h1><p>This is a starter template, not legal advice. The operator should review it for the deployment and jurisdiction before launch.</p></section>
    <section className="legal-content"><div className="notice-panel"><strong>Operator action required</strong><p>Add the operator's identity, effective date, contact details and any jurisdiction-specific terms before making this page public.</p></div>
      <h2>Permitted use</h2><p>Use the service only for lawful purposes and only upload content you are authorized to submit. Do not use the service to violate privacy, intellectual-property rights or applicable law.</p>
      <h2>Recognition limitations</h2><p>SceneSeek provides candidate matches, not guaranteed identifications. Results can be incomplete or incorrect, and titles outside the available reference collection may not be recognized. Do not rely on results for high-stakes decisions.</p>
      <h2>Availability and abuse</h2><p>The service may be unavailable, rate-limited or changed without notice. Do not attempt to bypass limits, disrupt the service, access other users' private data or probe administrative endpoints without authorization.</p>
      <h2>Third-party services and content</h2><p>Metadata, artwork and external links may be supplied by third parties and remain subject to their terms. SceneSeek should not be assumed to own the underlying films, series, anime, images or audio.</p>
      <h2>Feedback and removal requests</h2><p>Users may submit correction feedback or content-related requests through available mechanisms. The operator must review and respond using a documented process; submitting a request does not imply automatic approval or removal.</p>
    </section><footer className="footer compact-footer"><Link href="/" className="footer-brand"><span className="brand-word">Scene<span>Seek</span></span><small>SEE IT. SEEK IT. FIND IT.</small></Link><nav className="footer-links"><Link href="/help">Help</Link><Link href="/privacy">Privacy</Link><Link href="/stats">Evaluation</Link></nav></footer>
  </main>;
}
