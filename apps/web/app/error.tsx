'use client';

import Link from 'next/link';
import { useEffect } from 'react';

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <main className="shell subpage-shell" id="main">
      <div className="subpage-state">
        <span className="section-kicker">SOMETHING BROKE</span>
        <h1>That didn’t work.</h1>
        <p>An unexpected error occurred while showing this page. Your upload was not lost on our side — you can try again.</p>
        <div className="state-actions">
          <button type="button" className="primary-button" onClick={reset}>Try again</button>
          <Link href="/" className="secondary-button">Back to home</Link>
        </div>
      </div>
    </main>
  );
}
