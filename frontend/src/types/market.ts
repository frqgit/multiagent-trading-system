// ── Market data types mirroring backend StockSnapshot ──

export interface MarketData {
  symbol: string;
  company_name: string;
  sector: string;
  current_price: number;
  previous_close: number;
  open_price: number;
  day_high: number;
  day_low: number;
  week52_high: number;
  week52_low: number;
  volume: number;
  avg_volume: number;
  market_cap: number;
  pe_ratio: number | null;
  eps: number | null;
  dividend_yield: number | null;
  ma20: number;
  ma50: number;
  ma200: number;
  ema12: number;
  ema26: number;
  macd: number;
  macd_signal: number;
  rsi: number;
  volatility: number;
  beta: number | null;
  trend: 'strong_bullish' | 'bullish' | 'sideways' | 'bearish' | 'strong_bearish';
  price_change: number;
  price_change_pct: number;
  price_history_30d: PricePoint[];
  fetched_at: string;
}

export interface PricePoint {
  date: string;
  close: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
}

export interface WatchlistItem {
  symbol: string;
  company_name: string;
  current_price: number;
  price_change: number;
  price_change_pct: number;
  volume: number;
  trend: string;
}

export interface OrderBookLevel {
  price: number;
  quantity: number;
  total: number;
}

export interface OrderBook {
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  spread: number;
  spreadPct: number;
  lastPrice: number;
}

export interface CandlestickData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1D' | '1W' | '1M';
