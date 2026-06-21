// Reusable pill badge for strategy signal actions.
// BUY  → red  (gain token, matching the KR market convention used throughout the app)
// SELL → blue (loss token)
// HOLD → gray

import type { SignalAction } from '@/types/strategy';

interface SignalBadgeProps {
  action: SignalAction;
  className?: string;
}

const ACTION_CONFIG: Record<
  SignalAction,
  { label: string; colorClass: string }
> = {
  buy: {
    label: 'BUY',
    colorClass: 'border-red-200 bg-red-50 text-red-600',
  },
  sell: {
    label: 'SELL',
    colorClass: 'border-blue-200 bg-blue-50 text-blue-600',
  },
  hold: {
    label: 'HOLD',
    colorClass: 'border-gray-200 bg-gray-50 text-gray-500',
  },
};

export default function SignalBadge({ action, className = '' }: SignalBadgeProps) {
  const config = ACTION_CONFIG[action];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${config.colorClass} ${className}`}
    >
      {config.label}
    </span>
  );
}
