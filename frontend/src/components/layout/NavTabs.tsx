'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface NavTab {
  href: string;
  label: string;
  shortLabel: string;
}

const NAV_TABS: NavTab[] = [
  { href: '/dashboard', label: 'Dashboard', shortLabel: '홈' },
  { href: '/portfolio', label: 'Portfolio', shortLabel: '포트' },
  { href: '/strategy', label: 'Strategy', shortLabel: '전략' },
  { href: '/trading', label: 'Trading', shortLabel: '거래' },
];

export default function NavTabs() {
  const pathname = usePathname();

  return (
    <nav
      className="flex items-center gap-1"
      role="navigation"
      aria-label="Primary"
    >
      {NAV_TABS.map((tab) => {
        // Match exact path or any deeper segment. Avoids false positives on
        // hypothetical `/trading-view` style routes that would otherwise
        // trigger a greedy startsWith match.
        const isActive = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={isActive ? 'page' : undefined}
            className={
              isActive
                ? 'inline-flex items-center rounded-md bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm'
                : 'inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900'
            }
          >
            <span className="hidden sm:inline">{tab.label}</span>
            <span className="sm:hidden">{tab.shortLabel}</span>
          </Link>
        );
      })}
    </nav>
  );
}
