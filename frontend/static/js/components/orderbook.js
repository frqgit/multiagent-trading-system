// ── Order Book depth panel with bid/ask visualization (rAF batched) ──

import { store } from '../store.js';

export function initOrderBook() {
  const actionsEl = document.getElementById('orderbook-actions');
  const bodyEl = document.getElementById('orderbook-body');

  bodyEl.innerHTML = `
    <div class="ob-wrapper">
      <div class="ob-header-row">
        <span>Price</span>
        <span style="text-align:right">Qty</span>
        <span style="text-align:right">Total</span>
      </div>
      <div class="ob-section asks" id="ob-asks"></div>
      <div class="ob-spread" id="ob-spread-bar">
        <span class="ob-spread-price" id="ob-last-price">150.00</span>
        <span class="ob-spread-symbol" id="ob-symbol">AAPL</span>
      </div>
      <div class="ob-section" id="ob-bids"></div>
    </div>
  `;

  actionsEl.innerHTML = `
    <span style="font-size:10px;color:var(--text-muted)">
      Spread: <span id="ob-spread-text" style="font-family:var(--font-mono);color:var(--text-secondary)">0.02 (0.013%)</span>
    </span>
  `;

  const asksEl = bodyEl.querySelector('#ob-asks');
  const bidsEl = bodyEl.querySelector('#ob-bids');
  const lastPriceEl = bodyEl.querySelector('#ob-last-price');
  const symbolEl = bodyEl.querySelector('#ob-symbol');
  const spreadTextEl = actionsEl.querySelector('#ob-spread-text');

  let rafPending = false;

  function scheduleRender() {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(() => {
      rafPending = false;
      render();
    });
  }

  function render() {
    const book = store.get('orderBook');
    const sym = store.get('activeSymbol');
    const maxBid = book.bids.length > 0 ? book.bids[book.bids.length - 1].total : 1;
    const maxAsk = book.asks.length > 0 ? book.asks[book.asks.length - 1].total : 1;
    const maxTotal = Math.max(maxBid, maxAsk);

    renderLevels(asksEl, book.asks.slice(0, 12), maxTotal, 'ask', 'var(--color-sell)');
    renderLevels(bidsEl, book.bids.slice(0, 12), maxTotal, 'bid', 'var(--color-buy)');

    lastPriceEl.textContent = book.lastPrice.toFixed(2);
    symbolEl.textContent = sym;
    spreadTextEl.textContent = book.spread.toFixed(2) + ' (' + book.spreadPct.toFixed(3) + '%)';
  }

  store.on('orderBook', scheduleRender);
  store.on('activeSymbol', scheduleRender);
  render();
}

function renderLevels(container, levels, maxTotal, side, color) {
  // Reconcile DOM elements
  while (container.children.length > levels.length) {
    container.lastChild.remove();
  }

  levels.forEach((level, i) => {
    let el = container.children[i];
    if (!el) {
      el = document.createElement('div');
      el.className = 'ob-level';
      el.innerHTML = `
        <div class="ob-level-bg ${side}"></div>
        <span class="ob-price" style="font-family:var(--font-mono);font-weight:500;z-index:1"></span>
        <span class="ob-qty" style="text-align:right;font-family:var(--font-mono);color:var(--text-secondary);z-index:1"></span>
        <span class="ob-total" style="text-align:right;font-family:var(--font-mono);color:var(--text-muted);z-index:1"></span>
      `;
      container.appendChild(el);
    }

    el.querySelector('.ob-level-bg').style.width = ((level.total / maxTotal) * 100) + '%';
    const priceEl = el.querySelector('.ob-price');
    priceEl.textContent = level.price.toFixed(2);
    priceEl.style.color = color;
    el.querySelector('.ob-qty').textContent = level.quantity.toLocaleString();
    el.querySelector('.ob-total').textContent = level.total.toLocaleString();
  });
}
