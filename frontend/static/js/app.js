// ── App entry — initializes components + WebSocket data bindings ──

import { store } from './store.js';
import { marketWS, signalsWS, portfolioWS } from './websocket.js';
import { initHeader } from './components/header.js';
import { initSearch } from './components/search.js';
import { initChart } from './components/chart.js';
import { initWatchlist } from './components/watchlist.js';
import { initOrderBook } from './components/orderbook.js';
import { initSignals } from './components/signals.js';
import { initPortfolio } from './components/portfolio.js';

// ── Initialize UI components ──
initHeader();
initSearch();
initChart();
initWatchlist();
initOrderBook();
initSignals();
initPortfolio();

// ── WebSocket connections ──
let subscribed = false;

marketWS.connect();
signalsWS.connect();
portfolioWS.connect();

// Market data stream
marketWS.on('_connected', () => {
  store.setWsConnected(true);
  const symbols = store.get('watchlist').map(w => w.symbol);
  if (symbols.length > 0) {
    marketWS.send({ subscribe: symbols });
    subscribed = true;
  }
});

marketWS.on('_disconnected', () => {
  store.setWsConnected(false);
  subscribed = false;
});

marketWS.on('market_data', (msg) => {
  if (msg.symbol && msg.data) {
    store.updateMarketData(msg.symbol, msg.data);
  }
});

// AI signal stream
signalsWS.on('ai_signal', (msg) => {
  const data = msg.data;
  if (data) {
    store.addSignal({
      symbol: msg.symbol || '',
      action: data.action || 'HOLD',
      confidence: data.confidence || 0,
      reasoning: data.reasoning || '',
      key_factors: data.key_factors || [],
      suggested_entry: data.suggested_entry || null,
      target_price: data.target_price || null,
      stop_loss: data.stop_loss || null,
      time_horizon: data.time_horizon || null,
      timestamp: new Date().toISOString(),
    });
  }
});

// Portfolio stream
portfolioWS.on('portfolio_update', (msg) => {
  if (msg.data) store.updatePortfolio(msg.data);
});

// ── Reactive subscriptions for WebSocket re-sync ──

// Re-subscribe market data when watchlist changes
store.on('watchlist', () => {
  if (subscribed) {
    const symbols = store.get('watchlist').map(w => w.symbol);
    marketWS.send({ subscribe: symbols });
  }
});

// Subscribe AI signals to active symbol
store.on('activeSymbol', () => {
  const sym = store.get('activeSymbol');
  if (sym) signalsWS.send({ symbol: sym });
});
