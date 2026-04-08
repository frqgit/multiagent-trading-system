// ── AI Signals panel with confidence meters ──

import { store } from '../store.js';
import { api } from '../api.js';
import { getSignalColor, getSignalBadgeClass, getConfidenceColor, escapeHtml } from '../utils.js';

export function initSignals() {
  const actionsEl = document.getElementById('signals-actions');
  const bodyEl = document.getElementById('signals-body');

  // Analyze button
  actionsEl.innerHTML = `<button class="analyze-btn" id="analyze-btn">Analyze AAPL</button>`;
  const analyzeBtn = actionsEl.querySelector('#analyze-btn');

  analyzeBtn.addEventListener('click', async () => {
    const sym = store.get('activeSymbol');
    analyzeBtn.textContent = 'Analyzing…';
    analyzeBtn.disabled = true;
    try {
      const results = await api.analyze('Quick analysis ' + sym);
      if (results?.[0]) {
        const decision = results[0].decision ?? {};
        store.addSignal({
          symbol: sym,
          action: decision.action || 'HOLD',
          confidence: decision.confidence || 0,
          reasoning: decision.reasoning || '',
          key_factors: decision.key_factors || [],
          suggested_entry: decision.suggested_entry || null,
          target_price: decision.target_price || null,
          stop_loss: decision.suggested_stop_loss || null,
          time_horizon: decision.time_horizon || null,
          timestamp: new Date().toISOString(),
        });
      }
    } catch {
      // silently fail
    }
    analyzeBtn.textContent = 'Analyze ' + sym;
    analyzeBtn.disabled = false;
  });

  function render() {
    const signals = store.get('signals');

    if (signals.length === 0) {
      bodyEl.innerHTML = `
        <div class="signals-empty">
          <div style="font-size:24px;margin-bottom:8px">🤖</div>
          <div>No signals yet</div>
          <div style="font-size:11px;margin-top:4px">Click "Analyze" to generate AI signals</div>
        </div>
      `;
      return;
    }

    bodyEl.innerHTML =
      '<div class="signals-list">' +
      signals.map(sig => renderSignalCard(sig)).join('') +
      '</div>';

    // Attach click handlers via delegation
    bodyEl.querySelector('.signals-list').addEventListener('click', (e) => {
      const card = e.target.closest('.signal-card');
      if (card) store.setActiveSymbol(card.dataset.symbol);
    });
  }

  store.on('signals', render);
  store.on('activeSymbol', () => {
    analyzeBtn.textContent = 'Analyze ' + store.get('activeSymbol');
  });

  render();
}

function renderSignalCard(sig) {
  const borderColor = getSignalColor(sig.action);
  const badgeClass = getSignalBadgeClass(sig.action);
  const confColor = getConfidenceColor(sig.confidence);

  let targets = '';
  if (sig.suggested_entry || sig.target_price || sig.stop_loss) {
    targets = '<div class="signal-targets">';
    if (sig.suggested_entry) {
      targets += `<span style="color:var(--text-secondary)">Entry: <span class="mono" style="color:var(--text-primary)">$${sig.suggested_entry.toFixed(2)}</span></span>`;
    }
    if (sig.target_price) {
      targets += `<span style="color:var(--text-secondary)">Target: <span class="mono" style="color:var(--color-buy)">$${sig.target_price.toFixed(2)}</span></span>`;
    }
    if (sig.stop_loss) {
      targets += `<span style="color:var(--text-secondary)">Stop: <span class="mono" style="color:var(--color-sell)">$${sig.stop_loss.toFixed(2)}</span></span>`;
    }
    targets += '</div>';
  }

  let factors = '';
  if (sig.key_factors?.length) {
    factors =
      '<div class="signal-factors">' +
      sig.key_factors
        .slice(0, 3)
        .map(
          f =>
            `<span class="signal-factor-tag">${escapeHtml(f.length > 40 ? f.slice(0, 40) + '…' : f)}</span>`
        )
        .join('') +
      '</div>';
  }

  return `
    <div class="signal-card" data-symbol="${escapeHtml(sig.symbol)}" style="border-left:3px solid ${borderColor}">
      <div class="signal-card-header">
        <div style="display:flex;align-items:center;gap:8px">
          <span class="mono" style="font-weight:700;font-size:12px;color:var(--text-bright)">${escapeHtml(sig.symbol)}</span>
          <span class="${badgeClass}">${escapeHtml(sig.action.replace('_', ' '))}</span>
        </div>
        <span style="font-size:10px;color:var(--text-muted)">${new Date(sig.timestamp).toLocaleTimeString()}</span>
      </div>
      <div class="signal-confidence">
        <span style="font-size:10px;color:var(--text-muted);min-width:60px">Confidence</span>
        <div class="confidence-bar-track">
          <div class="confidence-bar-fill" style="width:${sig.confidence * 100}%;background:${confColor}"></div>
        </div>
        <span class="mono" style="font-size:11px;font-weight:600;color:${confColor};min-width:36px;text-align:right">${(sig.confidence * 100).toFixed(0)}%</span>
      </div>
      ${targets}
      ${factors}
    </div>
  `;
}
