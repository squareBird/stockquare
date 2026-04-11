import AccountStatus from './_components/AccountStatus';
import AccountSummary from './_components/AccountSummary';
import MarketIndex from './_components/MarketIndex';
import Watchlist from './_components/Watchlist';

export default function DashboardPage() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Dashboard</h1>
        <AccountStatus />
      </header>

      <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <AccountSummary />
        <MarketIndex />
      </section>

      <section>
        <Watchlist />
      </section>
    </main>
  );
}
