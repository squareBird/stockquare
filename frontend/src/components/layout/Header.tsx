import Link from 'next/link';

import HeaderAccount from './HeaderAccount';
import NavTabs from './NavTabs';

// Global top navigation. Renders the brand wordmark (monogram on mobile),
// the primary nav tabs, and the compact account/mode indicator.
// Horizontal at every breakpoint — there is no sidebar variant.
export default function Header() {
  return (
    <header className="sticky top-0 z-40 h-14 w-full border-b border-gray-200 bg-white">
      <div className="mx-auto flex h-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="flex items-center gap-2" aria-label="Stockquare home">
            <span
              className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-xs font-bold text-white sm:hidden"
              aria-hidden="true"
            >
              SQ
            </span>
            <span className="hidden text-base font-bold tracking-tight text-gray-900 sm:inline">
              Stockquare
            </span>
          </Link>
          <NavTabs />
        </div>
        <HeaderAccount />
      </div>
    </header>
  );
}
