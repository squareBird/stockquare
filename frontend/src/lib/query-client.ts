import { QueryClient } from '@tanstack/react-query';

// Shared QueryClient factory. Called once per React tree mount by the provider.
//
// Defaults tuned for the dashboard's polling UX:
// - `retry: 1` — TanStack Query's default is 3 with exponential backoff, which
//   keeps `isError` false for 10–30s after a failure. Users interpret that as
//   an infinite loading spinner. We fail fast after one retry (~1–2 s).
// - `retryDelay` — short exponential backoff capped at 3s so the single retry
//   still happens quickly.
// - `staleTime: 15_000` — suppress duplicate fetches during quick re-renders
//   while still letting the 30s poll produce fresh data.
// - `refetchOnWindowFocus: false` — the dashboard already polls on a timer;
//   a window-focus refetch would duplicate work and can briefly flash stale
//   skeletons during tab switches.
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 3000),
        staleTime: 15_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}
