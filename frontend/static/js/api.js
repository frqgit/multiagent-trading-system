// ── REST API client ──

const BASE = '/api/v1';

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  analyze: (message) =>
    request('/analyze', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  chat: (message, token) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }),

  getStrategies: () => request('/engine/strategies'),
  getIndicators: () => request('/engine/indicators'),

  getSignals: (symbol, strategy, period = '6mo') =>
    request('/engine/signals', {
      method: 'POST',
      body: JSON.stringify({ symbol, strategy_name: strategy, period }),
    }),

  backtest: (symbol, strategy, days = 365) =>
    request('/advanced/backtest', {
      method: 'POST',
      body: JSON.stringify({ symbol, strategy, days }),
    }),

  technical: (symbol, days = 90) =>
    request('/advanced/technical', {
      method: 'POST',
      body: JSON.stringify({ symbol, days }),
    }),

  portfolio: () => request('/advanced/execution/portfolio'),

  health: () => request('/health'),
};
