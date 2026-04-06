// ── AI signal types mirroring backend DecisionResponse ──

export type SignalAction = 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL';

export interface AISignal {
  symbol: string;
  action: SignalAction;
  confidence: number;
  reasoning: string;
  key_factors: string[];
  suggested_entry: number | null;
  target_price: number | null;
  stop_loss: number | null;
  time_horizon: string | null;
  timestamp: string;
}

export function getSignalColor(action: SignalAction): string {
  switch (action) {
    case 'STRONG_BUY':
    case 'BUY':
      return 'var(--color-buy)';
    case 'SELL':
    case 'STRONG_SELL':
      return 'var(--color-sell)';
    default:
      return 'var(--color-hold)';
  }
}

export function getSignalBadgeClass(action: SignalAction): string {
  if (action === 'STRONG_BUY' || action === 'BUY') return 'badge badge-buy';
  if (action === 'SELL' || action === 'STRONG_SELL') return 'badge badge-sell';
  return 'badge badge-hold';
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.7) return 'var(--signal-strong)';
  if (confidence >= 0.4) return 'var(--signal-moderate)';
  return 'var(--signal-weak)';
}
