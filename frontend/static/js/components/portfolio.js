// ── Portfolio panel with positions + P&L ──

import { store } from '../store.js';
import { formatNumber, escapeHtml } from '../utils.js';

export function initPortfolio() {
  const bodyEl = document.getElementById('portfolio-body');

  function render() {
    const { summary, positions, trade_statistics } = store.get('portfolio');

    const totalPnlColor =
      summary.unrealized_pnl > 0
        ? 'var(--color-buy)'
        : summary.unrealized_pnl < 0
        ? 'var(--color-sell)'
        : 'var(--text-secondary)';

    let positionsHtml;
    if (positions.length > 0) {
      positionsHtml = `
        <table class="positions-table">
          <thead>
            <tr>
              <th style="text-align:left">Symbol</th>
              <th style="text-align:right">Qty</th>
              <th style="text-align:right">Avg Cost</th>
              <th style="text-align:right">Mkt Value</th>
              <th style="text-align:right">P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            ${positions
              .map(pos => {
                const pnlColor =
                  pos.unrealized_pnl >= 0 ? 'var(--color-buy)' : 'var(--color-sell)';
                return `
                  <tr data-symbol="${escapeHtml(pos.symbol)}">
                    <td style="font-weight:600;color:var(--text-bright)">${escapeHtml(pos.symbol)}</td>
                    <td style="text-align:right;color:var(--text-secondary)">${pos.quantity}</td>
                    <td style="text-align:right;color:var(--text-secondary)">$${pos.avg_cost.toFixed(2)}</td>
                    <td style="text-align:right;color:var(--text-primary)">$${formatNumber(pos.market_value)}</td>
                    <td style="text-align:right;font-weight:600;color:${pnlColor}">
                      ${pos.unrealized_pnl >= 0 ? '+' : ''}$${formatNumber(pos.unrealized_pnl)}
                      <div style="font-size:9px;font-weight:400">
                        ${pos.unrealized_pnl_pct >= 0 ? '+' : ''}${pos.unrealized_pnl_pct.toFixed(2)}%
                      </div>
                    </td>
                  </tr>`;
              })
              .join('')}
          </tbody>
        </table>`;
    } else {
      positionsHtml = `
        <div class="positions-empty">
          <div style="font-size:20px;margin-bottom:8px">💼</div>
          No open positions
        </div>`;
    }

    bodyEl.innerHTML = `
      <div class="portfolio-content">
        <div class="portfolio-summary">
          <div class="summary-card">
            <div class="summary-card-label">Total Value</div>
            <div class="summary-card-value">$${formatNumber(summary.total_value)}</div>
          </div>
          <div class="summary-card">
            <div class="summary-card-label">Cash</div>
            <div class="summary-card-value">$${formatNumber(summary.cash)}</div>
          </div>
          <div class="summary-card">
            <div class="summary-card-label">Unrealized P&amp;L</div>
            <div class="summary-card-value" style="color:${totalPnlColor}">
              ${summary.unrealized_pnl >= 0 ? '+' : ''}$${formatNumber(summary.unrealized_pnl)}
            </div>
          </div>
        </div>
        <div class="trade-stats">
          <span style="color:var(--text-muted)">Win Rate:
            <span class="mono" style="color:var(--text-primary);font-weight:600">${(trade_statistics.win_rate * 100).toFixed(1)}%</span>
          </span>
          <span style="color:var(--text-muted)">Trades:
            <span class="mono" style="color:var(--text-primary);font-weight:600">${trade_statistics.total_trades}</span>
          </span>
          <span style="color:var(--text-muted)">Avg P&amp;L:
            <span class="mono" style="font-weight:600;color:${trade_statistics.avg_pnl >= 0 ? 'var(--color-buy)' : 'var(--color-sell)'}">
              $${trade_statistics.avg_pnl.toFixed(2)}
            </span>
          </span>
        </div>
        ${positionsHtml}
      </div>`;

    // Click handlers for position rows
    bodyEl.querySelectorAll('.positions-table tbody tr').forEach(row => {
      row.addEventListener('click', () => {
        store.setActiveSymbol(row.dataset.symbol);
      });
    });
  }

  store.on('portfolio', render);
  render();
}
