// Formatters shared across display components.

export function formatKrw(value: number): string {
  const formatted = Math.abs(value).toLocaleString('ko-KR');
  const sign = value < 0 ? '-' : '';
  return `${sign}₩${formatted}`;
}

export function formatSignedKrw(value: number): string {
  if (value === 0) return '₩0';
  const formatted = Math.abs(value).toLocaleString('ko-KR');
  const sign = value > 0 ? '+' : '-';
  return `${sign}₩${formatted}`;
}

export function formatSignedNumber(value: number, fractionDigits = 2): string {
  if (value === 0) return (0).toFixed(fractionDigits);
  const formatted = Math.abs(value).toLocaleString('ko-KR', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
  const sign = value > 0 ? '+' : '-';
  return `${sign}${formatted}`;
}

export function formatSignedPercent(value: number, fractionDigits = 2): string {
  if (value === 0) return `${(0).toFixed(fractionDigits)}%`;
  const sign = value > 0 ? '+' : '-';
  return `${sign}${Math.abs(value).toFixed(fractionDigits)}%`;
}

export function formatVolume(value: number): string {
  return value.toLocaleString('ko-KR');
}

export function formatIndexValue(value: number): string {
  return value.toLocaleString('ko-KR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function changeColorClass(value: number): string {
  if (value > 0) return 'text-red-500';
  if (value < 0) return 'text-blue-500';
  return 'text-gray-500';
}
