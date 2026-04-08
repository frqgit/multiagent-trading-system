// ── Shared utility functions ──

export function formatNumber(n) {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(2) + 'K';
  return n.toFixed(2);
}

export function formatVolume(v) {
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(1) + 'B';
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
  if (v >= 1_000) return (v / 1_000).toFixed(1) + 'K';
  return v.toString();
}

export function getSignalColor(action) {
  if (action === 'STRONG_BUY' || action === 'BUY') return 'var(--color-buy)';
  if (action === 'SELL' || action === 'STRONG_SELL') return 'var(--color-sell)';
  return 'var(--color-hold)';
}

export function getSignalBadgeClass(action) {
  if (action === 'STRONG_BUY' || action === 'BUY') return 'badge badge-buy';
  if (action === 'SELL' || action === 'STRONG_SELL') return 'badge badge-sell';
  return 'badge badge-hold';
}

export function getConfidenceColor(confidence) {
  if (confidence >= 0.7) return 'var(--signal-strong)';
  if (confidence >= 0.4) return 'var(--signal-moderate)';
  return 'var(--signal-weak)';
}

export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/** Simple moving average calculation for chart overlays */
export function calcSMA(data, period) {
  const result = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].value;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}
