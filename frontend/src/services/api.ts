// ── REST API client ──

const BASE = '/api/v1';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
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
  // Analysis
  analyze: (message: string) =>
    request<unknown[]>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  chat: (message: string, token?: string) =>
    request<Record<string, unknown>>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }),

  // Engine
  getStrategies: () => request<unknown>('/engine/strategies'),
  getIndicators: () => request<unknown>('/engine/indicators'),
  getSignals: (symbol: string, strategy: string, period: string = '6mo') =>
    request<unknown>('/engine/signals', {
      method: 'POST',
      body: JSON.stringify({ symbol, strategy_name: strategy, period }),
    }),

  // Advanced
  backtest: (symbol: string, strategy: string, days: number = 365) =>
    request<unknown>('/advanced/backtest', {
      method: 'POST',
      body: JSON.stringify({ symbol, strategy, days }),
    }),

  technical: (symbol: string, days: number = 90) =>
    request<unknown>('/advanced/technical', {
      method: 'POST',
      body: JSON.stringify({ symbol, days }),
    }),

  portfolio: (symbols: string[]) =>
    request<unknown>('/advanced/execution/portfolio', {
      method: 'GET',
    }),

  // Health
  health: () => request<{ status: string }>('/health'),
};
