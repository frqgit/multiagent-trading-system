// ── Header component with branding, active symbol ticker, connection status ──

import { store } from '../store.js';

export function initHeader() {
  const el = document.getElementById('app-header');

  el.innerHTML = `
    <div class="header-left">
      <div class="header-brand">
        <div class="brand-logo">TE</div>
        <span class="brand-name">TradingEdge</span>
        <span class="brand-badge">AI</span>
      </div>
      <div class="header-ticker" id="header-ticker" style="display:none">
        <span class="ticker-symbol mono" id="hdr-symbol"></span>
        <span class="ticker-price mono" id="hdr-price"></span>
        <span class="ticker-change mono" id="hdr-change"></span>
      </div>
    </div>
    <div class="header-center" id="search-container"></div>
    <div class="header-right">
      <div class="connection-status" id="conn-status">
        <div class="status-dot"></div>
        <span id="conn-text">OFFLINE</span>
      </div>
      <span class="header-clock mono" id="hdr-clock"></span>
    </div>
  `;

  // Cache DOM refs for targeted updates
  const tickerEl = el.querySelector('#header-ticker');
  const symEl = el.querySelector('#hdr-symbol');
  const priceEl = el.querySelector('#hdr-price');
  const changeEl = el.querySelector('#hdr-change');
  const connEl = el.querySelector('#conn-status');
  const connText = el.querySelector('#conn-text');
  const clockEl = el.querySelector('#hdr-clock');

  function updateTicker() {
    const sym = store.get('activeSymbol');
    const md = store.get('marketData')[sym];
    if (md) {
      tickerEl.style.display = '';
      symEl.textContent = sym;
      priceEl.textContent = '$' + md.current_price.toFixed(2);
      const up = md.price_change >= 0;
      changeEl.textContent =
        (up ? '+' : '') + md.price_change.toFixed(2) +
        ' (' + md.price_change_pct.toFixed(2) + '%)';
      changeEl.className = 'ticker-change mono ' + (up ? 'text-buy' : 'text-sell');
    } else {
      tickerEl.style.display = 'none';
    }
  }

  function updateConnection() {
    const connected = store.get('wsConnected');
    connEl.className = 'connection-status' + (connected ? ' connected' : '');
    connText.textContent = connected ? 'LIVE' : 'OFFLINE';
  }

  store.on('activeSymbol', updateTicker);
  store.on('marketData', updateTicker);
  store.on('wsConnected', updateConnection);

  updateTicker();
  updateConnection();

  // Live clock
  clockEl.textContent = new Date().toLocaleTimeString();
  setInterval(() => {
    clockEl.textContent = new Date().toLocaleTimeString();
  }, 1000);
}
