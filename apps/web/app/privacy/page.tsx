import Image from 'next/image';
import Link from 'next/link';

export const metadata = { title: 'Privacy — SceneSeek', description: 'Privacy and data-handling information for SceneSeek.' };

export default function PrivacyPage() {
  return <main className="shell subpage-shell legal-page">
    <header className="topbar"><Link href="/" className="brand"><Image src="/sceneseek-logo.png" width={56} height={56} alt="" unoptimized /><span className="brand-word">Scene<span>Seek</span></span></Link><Link href="/" className="back-link">← Back to search</Link></header>
    <section className="stats-hero"><span className="section-kicker">PRIVACY</span><h1>Your uploads deserve care.</h1><p>This page is a project template. The operator must verify and update it to match the deployed configuration before public launch.</p></section>
    <section className="legal-content"><div className="notice-panel"><strong>Operator action required</strong><p>Replace this template with a reviewed policy that names the responsible operator, contact method, retention periods, legal basis where applicable, and all active service providers. Do not publish unverified promises.</p></div>
      <h2>Information processed</h2><p>Depending on configuration, SceneSeek may process uploaded images or video clips, file metadata and hashes, job status and results, search history associated with a signed-in account, feedback, and basic request/security logs.</p>
      <h2>Third-party processing</h2><p>If online anime recognition is enabled, selected frames may be sent to trace.moe. Metadata lookups may contact external providers such as AniList, TVmaze, Apple search or OMDb depending on configuration. Google sign-in sends credentials to the API for verification. Confirm each provider's current terms and privacy practices before launch.</p>
      <h2>Retention and deletion</h2><p>The application is designed to delete temporary uploads after processing/retention cleanup, but operators must verify cleanup jobs and the storage backend in production. Database records, logs, backups and third-party records can have separate retention periods. Document actual values here.</p>
      <h2>Security</h2><p>Use private storage, HTTPS, server-side authorization, protected secrets, dependency updates and tested backups. Do not upload sensitive personal content unless the deployment's data handling has been reviewed.</p>
      <h2>Contact and requests</h2><p>Add the operator's monitored contact address and the process for data access/deletion and rights-holder requests before launch.</p>
    </section><footer className="footer compact-footer"><Link href="/" className="footer-brand"><span className="brand-word">Scene<span>Seek</span></span><small>SEE IT. SEEK IT. FIND IT.</small></Link><nav className="footer-links"><Link href="/help">Help</Link><Link href="/terms">Terms</Link><Link href="/stats">Evaluation</Link></nav></footer>
  </main>;
}
