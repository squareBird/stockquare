import type { ReactNode } from 'react';

import type { Metadata } from 'next';

import Providers from './providers';

import './globals.css';

export const metadata: Metadata = {
  title: 'Stockquare',
  description: 'Stock trading dashboard powered by KIS Open API',
};

interface RootLayoutProps {
  children: ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
