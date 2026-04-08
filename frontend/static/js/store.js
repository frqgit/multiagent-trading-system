// ── Reactive state store with event-driven updateUI pattern ──

const DEFAULT_WATCHLIST = [
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

function generateOrderBook(price) {
  const bids = [];
  const asks = [];
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

// ── Internal state ──
const state = {
  activeSymbol: 'AAPL',
  timeframe: '1D',
  watchlist: DEFAULT_WATCHLIST.map(w => ({ ...w })),
  marketData: {},
  orderBook: generateOrderBook(150),
  signals: [],
  portfolio: {
    summary: { cash: 100000, equity: 0, total_value: 100000, unrealized_pnl: 0, day_pnl: 0, day_pnl_pct: 0 },
    positions: [],
    open_orders: 0,
    trade_statistics: { win_rate: 0, total_trades: 0, avg_pnl: 0 },
  },
  wsConnected: false,
};

// ── Listener registry ──
const listeners = new Map();

function emit(key) {
  const fns = listeners.get(key);
  if (fns) fns.forEach(fn => fn(state[key]));
}

// ── Public store API ──
export const store = {
  get(key) {
    return state[key];
  },

  on(key, fn) {
    if (!listeners.has(key)) listeners.set(key, new Set());
    listeners.get(key).add(fn);
    return () => listeners.get(key).delete(fn);
  },

  setActiveSymbol(sym) {
    state.activeSymbol = sym;
    const price = state.marketData[sym]?.current_price || 150;
    state.orderBook = generateOrderBook(price);
    emit('activeSymbol');
    emit('orderBook');
  },

  setTimeframe(tf) {
    state.timeframe = tf;
    emit('timeframe');
  },

  addToWatchlist(symbol) {
    if (state.watchlist.some(w => w.symbol === symbol)) return;
    state.watchlist.push({
      symbol,
      company_name: symbol,
      current_price: 0,
      price_change: 0,
      price_change_pct: 0,
      volume: 0,
      trend: 'sideways',
    });
    emit('watchlist');
  },

  removeFromWatchlist(symbol) {
    state.watchlist = state.watchlist.filter(w => w.symbol !== symbol);
    emit('watchlist');
  },

  updateMarketData(symbol, data) {
    state.marketData[symbol] = data;

    // Sync watchlist item
    const idx = state.watchlist.findIndex(w => w.symbol === symbol);
    if (idx >= 0) {
      const w = state.watchlist[idx];
      w.current_price = data.current_price;
      w.price_change = data.price_change;
      w.price_change_pct = data.price_change_pct;
      w.volume = data.volume;
      w.trend = data.trend;
      w.company_name = data.company_name;
    }

    // Refresh order book for active symbol
    if (symbol === state.activeSymbol) {
      state.orderBook = generateOrderBook(data.current_price);
      emit('orderBook');
    }

    emit('marketData');
    emit('watchlist');
  },

  addSignal(signal) {
    state.signals = [signal, ...state.signals.filter(s => s.symbol !== signal.symbol)].slice(0, 50);
    emit('signals');
  },

  updatePortfolio(data) {
    if (data.summary) Object.assign(state.portfolio.summary, data.summary);
    if (data.positions) state.portfolio.positions = data.positions;
    if (data.trade_statistics) Object.assign(state.portfolio.trade_statistics, data.trade_statistics);
    emit('portfolio');
  },

  setWsConnected(v) {
    state.wsConnected = v;
    emit('wsConnected');
  },
};
