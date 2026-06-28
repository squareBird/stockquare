import { Suspense } from 'react';

import ModeBanner from './_components/ModeBanner';
import TradingWorkspace from './_components/TradingWorkspace';

export default function TradingPage() {
  return (
    <>
      <ModeBanner />
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
        <header>
          <h1 className="text-xl font-bold tracking-tight text-gray-900">Trading</h1>
        </header>
        {/* TradingWorkspace reads `?symbol=&interval=` via useSearchParams,
            which requires a Suspense boundary during SSR/prerender. */}
        <Suspense fallback={null}>
          <TradingWorkspace />
        </Suspense>
      </main>
    </>
  );
}
