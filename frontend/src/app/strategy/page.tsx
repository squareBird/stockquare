import StrategyWorkspace from './_components/StrategyWorkspace';

export default function StrategyPage() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
      <header>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Strategy</h1>
      </header>
      <StrategyWorkspace />
    </main>
  );
}
