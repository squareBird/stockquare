import { create } from 'zustand';

export type WatchlistSortKey = 'name' | 'changeRate' | 'price';
export type SortOrder = 'asc' | 'desc';

interface DashboardUIState {
  watchlistSortKey: WatchlistSortKey;
  watchlistSortOrder: SortOrder;
  setWatchlistSort: (key: WatchlistSortKey) => void;
}

export const useDashboardUI = create<DashboardUIState>((set) => ({
  watchlistSortKey: 'changeRate',
  watchlistSortOrder: 'desc',
  setWatchlistSort: (key) =>
    set((state) => {
      if (state.watchlistSortKey === key) {
        return {
          watchlistSortKey: key,
          watchlistSortOrder: state.watchlistSortOrder === 'asc' ? 'desc' : 'asc',
        };
      }
      return { watchlistSortKey: key, watchlistSortOrder: 'desc' };
    }),
}));
