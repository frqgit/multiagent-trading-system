// ── Watchlist with real-time price updates (DOM-patching, rAF batched) ──

import { store } from '../store.js';
import { formatVolume } from '../utils.js';

export function initWatchlist() {
  const body = document.getElementById('watchlist-body');

  body.innerHTML = `
    <table class="watchlist-table">
      <thead>
        <tr>
          <th style="text-align:left">Symbol</th>
          <th>Last</th>
          <th>Chg</th>
          <th>Chg%</th>
          <th>Vol</th>
          <th style="width:24px"></th>
        </tr>
      </thead>
      <tbody id="watchlist-tbody"></tbody>
    </table>
  `;

  const tbody = body.querySelector('#watchlist-tbody');
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
    const items = store.get('watchlist');
    const activeSym = store.get('activeSymbol');

    // Remove excess rows
    while (tbody.children.length > items.length) {
      tbody.lastChild.remove();
    }

    items.forEach((item, i) => {
      let row = tbody.children[i];
      if (!row) {
        row = document.createElement('tr');
        row.innerHTML = `
          <td><div class="wl-symbol"></div><div class="wl-company"></div></td>
          <td class="wl-price" style="text-align:right;font-family:var(--font-mono);font-weight:500;color:var(--text-bright)"></td>
          <td class="wl-chg" style="text-align:right;font-family:var(--font-mono)"></td>
          <td class="wl-chgpct" style="text-align:right;font-family:var(--font-mono);font-weight:500"></td>
          <td class="wl-vol" style="text-align:right;font-family:var(--font-mono);color:var(--text-secondary);font-size:11px"></td>
          <td style="text-align:center"><button class="wl-remove" title="Remove">×</button></td>
        `;
        tbody.appendChild(row);

        row.addEventListener('click', (e) => {
          if (e.target.closest('.wl-remove')) return;
          store.setActiveSymbol(row.dataset.symbol);
        });
        row.querySelector('.wl-remove').addEventListener('click', (e) => {
          e.stopPropagation();
          store.removeFromWatchlist(row.dataset.symbol);
        });
      }

      // Patch row data
      row.dataset.symbol = item.symbol;
      const isActive = item.symbol === activeSym;
      const isPos = item.price_change >= 0;
      const color =
        item.current_price === 0
          ? 'var(--text-muted)'
          : isPos
          ? 'var(--color-buy)'
          : 'var(--color-sell)';

      row.style.background = isActive ? 'var(--bg-hover)' : '';
      row.style.borderLeft = isActive ? '2px solid var(--accent-blue)' : '2px solid transparent';

      const symEl = row.querySelector('.wl-symbol');
      symEl.textContent = item.symbol;
      symEl.style.color = isActive ? 'var(--accent-blue)' : 'var(--text-bright)';

      row.querySelector('.wl-company').textContent = item.company_name;
      row.querySelector('.wl-price').textContent =
        item.current_price > 0 ? '$' + item.current_price.toFixed(2) : '—';

      const chgEl = row.querySelector('.wl-chg');
      chgEl.textContent =
        item.current_price > 0 ? (isPos ? '+' : '') + item.price_change.toFixed(2) : '—';
      chgEl.style.color = color;

      const pctEl = row.querySelector('.wl-chgpct');
      pctEl.textContent =
        item.current_price > 0
          ? (isPos ? '+' : '') + item.price_change_pct.toFixed(2) + '%'
          : '—';
      pctEl.style.color = color;

      row.querySelector('.wl-vol').textContent =
        item.volume > 0 ? formatVolume(item.volume) : '—';
    });
  }

  store.on('watchlist', scheduleRender);
  store.on('activeSymbol', scheduleRender);
  render();
}
