import SiteFooter from '../../components/SiteFooter';
import SiteHeader from '../../components/SiteHeader';
import Link from 'next/link';

export const metadata = { title: 'Help — SceneSeek', description: 'How to use SceneSeek and troubleshoot scene identification.' };

export default function HelpPage() {
  return <main className="shell subpage-shell legal-page" id="main">
    <SiteHeader />
    <section className="stats-hero"><span className="section-kicker">HELP CENTER</span><h1>Find the best clue.</h1><p>Tips for getting a useful match from a screenshot or short clip.</p></section>
    <section className="legal-content">
      <h2>Supported uploads</h2><p>SceneSeek accepts JPG, PNG and WEBP images up to 10 MB, and MP4, WEBM and MOV clips up to 25 MB and 30 seconds. Actual format validation is performed by the server.</p>
      <h2>Improve your match</h2><ul><li>Choose a clear frame with recognizable characters, scenery or objects.</li><li>Avoid heavy filters, large stickers, borders and overlays when possible.</li><li>For video, use a short clip with multiple useful frames rather than a blank transition.</li><li>Try a second frame if the result is ambiguous.</li></ul>
      <h2>Why did no match appear?</h2><p>Movie and series scene recognition depends on the titles and frames available in the reference index. A title missing from that index may not be found. Online anime matching can also be affected by third-party service availability.</p>
      <h2>Privacy and uploads</h2><p>Uploads are processed to identify a scene and are intended to be temporary. If online anime lookup is enabled, selected frames may be sent to the configured third-party recognition provider. Review the <Link href="/privacy">Privacy page</Link> and the deployment configuration before uploading sensitive material.</p>
      <h2>Still stuck?</h2><p>For a reproducible bug report, include the page, approximate time, browser, and error message. Do not include passwords, access tokens or private API keys.</p>
    </section><SiteFooter compact />
  </main>;
}
