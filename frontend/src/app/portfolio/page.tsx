import AccountSummary from '../dashboard/_components/AccountSummary';

import AllocationSection from './_components/AllocationSection';
import HoldingsSection from './_components/HoldingsSection';

export default function PortfolioPage() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
      <header>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Portfolio</h1>
      </header>

      <section>
        <AccountSummary />
      </section>

      <section>
        <AllocationSection />
      </section>

      <section>
        <HoldingsSection />
      </section>
    </main>
  );
}
