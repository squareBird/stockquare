import { create } from 'zustand';

// Global UI store for the stock detail / chart modal. Any symbol-click target
// (watchlist row, search result, holding row) calls `open(symbol, name)`; the
// modal is mounted once near the root and reads `activeSymbol` / `activeName`.
interface StockDetailState {
  activeSymbol: string | null;
  activeName: string | null;
  open: (symbol: string, name: string) => void;
  close: () => void;
}

export const useStockDetail = create<StockDetailState>((set) => ({
  activeSymbol: null,
  activeName: null,
  open: (symbol, name) => set({ activeSymbol: symbol, activeName: name }),
  close: () => set({ activeSymbol: null, activeName: null }),
}));
