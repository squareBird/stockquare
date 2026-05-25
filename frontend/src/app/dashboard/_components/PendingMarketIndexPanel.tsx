type PendingCountry = 'US' | 'JP' | 'CN';

interface PendingMarketIndexPanelProps {
  country: PendingCountry;
}

// Placeholder labels for tabs that do not yet have a backend feed. These
// mirror the index families the backend plans to cover so users understand
// which markets they are waiting for.
const PENDING_LABELS: Record<PendingCountry, string> = {
  US: 'US · S&P 500 / Dow / Nasdaq',
  JP: 'Japan · Nikkei 225 / TOPIX',
  CN: 'China · Shanghai / Hang Seng',
};

// Static skeleton shown for tabs whose backend contract is still being
// designed. We render two ghost cards so the layout matches the KR panel
// and a one-line message explains why no data is available yet.
export default function PendingMarketIndexPanel({ country }: PendingMarketIndexPanelProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" aria-hidden="true">
        <div className="h-24 animate-pulse rounded-lg bg-gray-100" />
        <div className="h-24 animate-pulse rounded-lg bg-gray-100" />
      </div>
      <p className="text-xs text-gray-500">
        {PENDING_LABELS[country]} — Backend feed in progress
      </p>
    </div>
  );
}
