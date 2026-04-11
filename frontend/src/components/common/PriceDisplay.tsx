import { formatKrw } from '@/lib/format';

interface PriceDisplayProps {
  value: number;
  className?: string;
}

export default function PriceDisplay({ value, className = 'tabular-nums' }: PriceDisplayProps) {
  return <span className={className}>{formatKrw(value)}</span>;
}
