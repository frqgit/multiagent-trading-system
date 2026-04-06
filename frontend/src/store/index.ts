// ── Global application store (Zustand) ──

import { create } from 'zustand';
import type { MarketData, WatchlistItem, OrderBook, OrderBookLevel, Timeframe } from '../types/market';
import type { AISignal } from '../types/signals';
import type { PortfolioState, Position, PortfolioSummary } from '../types/portfolio';

interface AppState {
  // Active symbol
  activeSymbol: string;
  setActiveSymbol: (sym: string) => void;

  // Timeframe
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;

  // Watchlist
  watchlist: WatchlistItem[];
  updateWatchlistItem: (item: WatchlistItem) => void;
  addToWatchlist: (symbol: string) => void;
  removeFromWatchlist: (symbol: string) => void;

  // Market data cache
  marketData: Record<string, MarketData>;
  updateMarketData: (symbol: string, data: MarketData) => void;

  // Order book
  orderBook: OrderBook;
  updateOrderBook: (book: Partial<OrderBook>) => void;

  // AI Signals
  signals: AISignal[];
  addSignal: (signal: AISignal) => void;

  // Portfolio
  portfolio: PortfolioState;
  updatePortfolio: (data: Partial<PortfolioState>) => void;

  // Connection status
  wsConnected: boolean;
  setWsConnected: (v: boolean) => void;

  // Panel visibility
  panels: Record<string, boolean>;
  togglePanel: (id: string) => void;
}

const DEFAULT_WATCHLIST: WatchlistItem[] = [
  { symbol: 'AAPL', company_name: 'Apple Inc.', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'MSFT', company_name: 'Microsoft Corp', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'GOOGL', company_name: 'Alphabet Inc.', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'AMZN', company_name: 'Amazon.com Inc', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'TSLA', company_name: 'Tesla Inc.', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'NVDA', company_name: 'NVIDIA Corp', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'META', company_name: 'Meta Platforms', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'BHP.AX', company_name: 'BHP Group Ltd', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'CBA.AX', company_name: 'CommBank', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
  { symbol: 'CSL.AX', company_name: 'CSL Limited', current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' },
];

function generateOrderBook(price: number): OrderBook {
  const bids: OrderBookLevel[] = [];
  const asks: OrderBookLevel[] = [];
  let bidTotal = 0;
  let askTotal = 0;
  for (let i = 0; i < 15; i++) {
    const bidQty = Math.floor(Math.random() * 5000) + 100;
    const askQty = Math.floor(Math.random() * 5000) + 100;
    bidTotal += bidQty;
    askTotal += askQty;
    bids.push({ price: +(price - (i + 1) * 0.01).toFixed(2), quantity: bidQty, total: bidTotal });
    asks.push({ price: +(price + (i + 1) * 0.01).toFixed(2), quantity: askQty, total: askTotal });
  }
  const spread = asks[0].price - bids[0].price;
  return { bids, asks, spread: +spread.toFixed(4), spreadPct: +((spread / price) * 100).toFixed(4), lastPrice: price };
}

const DEFAULT_PORTFOLIO: PortfolioState = {
  summary: { cash: 100000, equity: 0, total_value: 100000, unrealized_pnl: 0, day_pnl: 0, day_pnl_pct: 0 },
  positions: [],
  open_orders: 0,
  trade_statistics: { win_rate: 0, total_trades: 0, avg_pnl: 0 },
};

export const useStore = create<AppState>((set) => ({
  activeSymbol: 'AAPL',
  setActiveSymbol: (sym) =>
    set((s) => {
      const price = s.marketData[sym]?.current_price || 150;
      return { activeSymbol: sym, orderBook: generateOrderBook(price) };
    }),

  timeframe: '1D',
  setTimeframe: (tf) => set({ timeframe: tf }),

  watchlist: DEFAULT_WATCHLIST,
  updateWatchlistItem: (item) =>
    set((s) => ({
      watchlist: s.watchlist.map((w) => (w.symbol === item.symbol ? { ...w, ...item } : w)),
    })),
  addToWatchlist: (symbol) =>
    set((s) => {
      if (s.watchlist.some((w) => w.symbol === symbol)) return s;
      return { watchlist: [...s.watchlist, { symbol, company_name: symbol, current_price: 0, price_change: 0, price_change_pct: 0, volume: 0, trend: 'sideways' }] };
    }),
  removeFromWatchlist: (symbol) =>
    set((s) => ({ watchlist: s.watchlist.filter((w) => w.symbol !== symbol) })),

  marketData: {},
  updateMarketData: (symbol, data) =>
    set((s) => {
      const newState: Partial<AppState> = { marketData: { ...s.marketData, [symbol]: data } };
      // Update watchlist item too
      const wItem = s.watchlist.find((w) => w.symbol === symbol);
      if (wItem) {
        newState.watchlist = s.watchlist.map((w) =>
          w.symbol === symbol
            ? { ...w, current_price: data.current_price, price_change: data.price_change, price_change_pct: data.price_change_pct, volume: data.volume, trend: data.trend, company_name: data.company_name }
            : w
        );
      }
      // Update order book for active symbol
      if (symbol === s.activeSymbol) {
        newState.orderBook = generateOrderBook(data.current_price);
      }
      return newState as AppState;
    }),

  orderBook: generateOrderBook(150),
  updateOrderBook: (book) => set((s) => ({ orderBook: { ...s.orderBook, ...book } })),

  signals: [],
  addSignal: (signal) =>
    set((s) => ({
      signals: [signal, ...s.signals.filter((sig) => sig.symbol !== signal.symbol)].slice(0, 50),
    })),

  portfolio: DEFAULT_PORTFOLIO,
  updatePortfolio: (data) =>
    set((s) => ({
      portfolio: {
        ...s.portfolio,
        ...data,
        summary: { ...s.portfolio.summary, ...(data.summary || {}) } as PortfolioSummary,
        positions: data.positions ?? s.portfolio.positions,
      },
    })),

  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  panels: { watchlist: true, chart: true, orderbook: true, signals: true, portfolio: true },
  togglePanel: (id) => set((s) => ({ panels: { ...s.panels, [id]: !s.panels[id] } })),
}));
