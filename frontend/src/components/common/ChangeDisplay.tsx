import {
  changeColorClass,
  formatSignedKrw,
  formatSignedPercent,
} from '@/lib/format';

interface ChangeDisplayProps {
  amount: number;
  rate: number;
  // When true, renders the amount with the ₩ currency prefix.
  // When false (used for index cards), renders the bare numeric change.
  currency?: boolean;
  className?: string;
}

export default function ChangeDisplay({
  amount,
  rate,
  currency = true,
  className = '',
}: ChangeDisplayProps) {
  const colorClass = changeColorClass(rate);
  const amountLabel = currency
    ? formatSignedKrw(amount)
    : amount.toLocaleString('ko-KR', {
        signDisplay: 'exceptZero',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

  return (
    <span className={`inline-flex items-baseline gap-1.5 tabular-nums ${colorClass} ${className}`}>
      <span>{amountLabel}</span>
      <span className="text-xs opacity-80">({formatSignedPercent(rate)})</span>
    </span>
  );
}
