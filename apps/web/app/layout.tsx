import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SceneSeek — See it. Seek it. Find it.',
  description: 'Discover the movie, series, or anime behind a screenshot or short clip.',
  applicationName: 'SceneSeek',
  icons: { icon: '/sceneseek-logo.png', shortcut: '/sceneseek-logo.png', apple: '/sceneseek-logo.png' },
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'),
  openGraph: {
    title: 'SceneSeek — See it. Seek it. Find it.',
    description: 'Find the title behind the scene.',
    images: ['/sceneseek-logo.png'],
    type: 'website',
  },
};

export const viewport: Viewport = {
  themeColor: '#070714',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="ambient ambient-blue" aria-hidden="true" />
        <div className="ambient ambient-purple" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
