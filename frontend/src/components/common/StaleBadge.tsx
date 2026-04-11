import WarningIcon from './WarningIcon';

// Small warning chip shown in the corner of a card when the last refetch
// failed but cached data is still being rendered. Keeps the user informed
// that the values may not reflect the latest market snapshot.
//
// Live-region semantics: role="status" is an implicit polite live region.
// The "Stale" text never changes once mounted; the badge re-announces on
// each mount/unmount cycle, which is the intended behavior. Do NOT change
// the inner text dynamically — `aria-label` updates are not re-announced.

interface StaleBadgeProps {
  className?: string;
}

export default function StaleBadge({ className = '' }: StaleBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 ${className}`}
      role="status"
      aria-label="Refresh failed; showing last known data"
      title="Refresh failed; showing last known data"
    >
      <WarningIcon size={10} />
      Stale
    </span>
  );
}
