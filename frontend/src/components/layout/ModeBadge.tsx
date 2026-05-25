'use client';

import type { AccountMode } from '@/types/dashboard';

interface ModeBadgeProps {
  mode: AccountMode | undefined;
}

// Small pill shown in the global header to communicate whether the user is
// trading against the real KIS account or the mock simulator. The dedicated
// full-width REAL banner on the Trading page is a separate component.
export default function ModeBadge({ mode }: ModeBadgeProps) {
  if (mode === undefined) return null;

  if (mode === 'real') {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-surface-inverse px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white"
        role="status"
        aria-label="Real trading mode"
      >
        <span
          className="h-1.5 w-1.5 rounded-full bg-gain"
          aria-hidden="true"
        />
        REAL
      </span>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-dashed border-gray-300 bg-gray-50 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-gray-500"
      role="status"
      aria-label="Mock simulator mode"
    >
      MOCK
    </span>
  );
}
