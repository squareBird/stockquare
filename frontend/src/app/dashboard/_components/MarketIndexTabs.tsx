'use client';

import type { KeyboardEvent } from 'react';

import type { Country } from '@/types/dashboard';

interface MarketIndexTabsProps {
  active: Country;
  onChange: (country: Country) => void;
}

const TABS: ReadonlyArray<{ country: Country; label: string }> = [
  { country: 'KR', label: 'KR' },
  { country: 'US', label: 'US' },
  { country: 'JP', label: 'JP' },
  { country: 'CN', label: 'CN' },
];

// Pill-style tab strip for the MarketIndex card. Uses the WAI-ARIA tabs
// pattern so screen readers expose the active tab + panel relationship.
// The matching tabpanel id/labelledby lives on the container in MarketIndex.
export default function MarketIndexTabs({ active, onChange }: MarketIndexTabsProps) {
  // WAI-ARIA tabs keyboard support: ← / → cycle, Home / End jump to ends.
  // Typing these keys on an active tab moves focus + selection to the
  // neighbor. Roving tabIndex keeps the inactive tabs out of the tab order
  // so Tab jumps straight to the panel content.
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const currentIndex = TABS.findIndex((tab) => tab.country === active);
    if (currentIndex < 0) return;

    let nextIndex = currentIndex;
    switch (event.key) {
      case 'ArrowRight':
        nextIndex = (currentIndex + 1) % TABS.length;
        break;
      case 'ArrowLeft':
        nextIndex = (currentIndex - 1 + TABS.length) % TABS.length;
        break;
      case 'Home':
        nextIndex = 0;
        break;
      case 'End':
        nextIndex = TABS.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    const nextTab = TABS[nextIndex];
    if (!nextTab) return;
    onChange(nextTab.country);
    const nextButton = document.getElementById(
      `market-tab-${nextTab.country.toLowerCase()}`,
    );
    nextButton?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label="Market country"
      className="flex gap-1 rounded-lg bg-gray-100 p-1"
    >
      {TABS.map(({ country, label }) => {
        const isActive = country === active;
        return (
          <button
            key={country}
            type="button"
            role="tab"
            id={`market-tab-${country.toLowerCase()}`}
            aria-selected={isActive}
            aria-controls={`market-panel-${country.toLowerCase()}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(country)}
            onKeyDown={handleKeyDown}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              isActive
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
