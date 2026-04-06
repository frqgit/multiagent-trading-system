// ── Portfolio types ──

export interface Position {
  symbol: string;
  quantity: number;
  avg_cost: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  current_price: number;
}

export interface PortfolioSummary {
  cash: number;
  equity: number;
  total_value: number;
  unrealized_pnl: number;
  day_pnl: number;
  day_pnl_pct: number;
}

export interface PortfolioState {
  summary: PortfolioSummary;
  positions: Position[];
  open_orders: number;
  trade_statistics: {
    win_rate: number;
    total_trades: number;
    avg_pnl: number;
  };
}
