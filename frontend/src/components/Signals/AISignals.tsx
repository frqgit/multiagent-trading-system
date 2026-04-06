// ── AI Signals panel with confidence meters ──

import React, { useCallback } from 'react';
import { PanelWrapper } from '../Layout/PanelWrapper';
import { useStore } from '../../store';
import { getSignalColor, getSignalBadgeClass, getConfidenceColor, type AISignal } from '../../types/signals';
import { api } from '../../services/api';

export const AISignals: React.FC = () => {
  const signals = useStore((s) => s.signals);
  const activeSymbol = useStore((s) => s.activeSymbol);
  const addSignal = useStore((s) => s.addSignal);

  const fetchSignal = useCallback(async () => {
    try {
      const results = (await api.analyze(`Quick analysis ${activeSymbol}`)) as Record<string, unknown>[];
      if (results?.[0]) {
        const r = results[0];
        const decision = (r.decision ?? {}) as Record<string, unknown>;
        addSignal({
          symbol: activeSymbol,
          action: (decision.action as AISignal['action']) ?? 'HOLD',
          confidence: (decision.confidence as number) ?? 0,
          reasoning: (decision.reasoning as string) ?? '',
          key_factors: (decision.key_factors as string[]) ?? [],
          suggested_entry: (decision.suggested_entry as number) ?? null,
          target_price: (decision.target_price as number) ?? null,
          stop_loss: (decision.suggested_stop_loss as number) ?? null,
          time_horizon: (decision.time_horizon as string) ?? null,
          timestamp: new Date().toISOString(),
        });
      }
    } catch {
      // silently fail
    }
  }, [activeSymbol, addSignal]);

  return (
    <PanelWrapper
      title="AI Signals"
      icon="🤖"
      actions={
        <button
          onClick={fetchSignal}
          style={{
            padding: '2px 8px',
            fontSize: 10,
            fontWeight: 600,
            background: 'var(--accent-blue-dim)',
            color: 'var(--accent-blue)',
            border: '1px solid var(--accent-blue)',
            borderRadius: 3,
            cursor: 'pointer',
          }}
        >
          Analyze {activeSymbol}
        </button>
      }
    >
      <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {signals.length === 0 ? (
          <div
            style={{
              padding: 24,
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: 12,
            }}
          >
            <div style={{ fontSize: 24, marginBottom: 8 }}>🤖</div>
            <div>No signals yet</div>
            <div style={{ fontSize: 11, marginTop: 4 }}>Click "Analyze" to generate AI signals</div>
          </div>
        ) : (
          signals.map((sig) => <SignalCard key={`${sig.symbol}-${sig.timestamp}`} signal={sig} />)
        )}
      </div>
    </PanelWrapper>
  );
};

const SignalCard: React.FC<{ signal: AISignal }> = ({ signal }) => {
  const setActiveSymbol = useStore((s) => s.setActiveSymbol);

  return (
    <div
      onClick={() => setActiveSymbol(signal.symbol)}
      style={{
        padding: '8px 10px',
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        borderLeft: `3px solid ${getSignalColor(signal.action)}`,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12, color: 'var(--text-bright)' }}>
            {signal.symbol}
          </span>
          <span className={getSignalBadgeClass(signal.action)}>{signal.action.replace('_', ' ')}</span>
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {new Date(signal.timestamp).toLocaleTimeString()}
        </span>
      </div>

      {/* Confidence bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 60 }}>Confidence</span>
        <div style={{ flex: 1, height: 4, background: 'var(--bg-primary)', borderRadius: 2 }}>
          <div
            style={{
              width: `${signal.confidence * 100}%`,
              height: '100%',
              background: getConfidenceColor(signal.confidence),
              borderRadius: 2,
              transition: 'width 0.3s',
            }}
          />
        </div>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 600,
            color: getConfidenceColor(signal.confidence),
            minWidth: 36,
            textAlign: 'right',
          }}
        >
          {(signal.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Price targets */}
      {(signal.suggested_entry || signal.target_price || signal.stop_loss) && (
        <div style={{ display: 'flex', gap: 12, fontSize: 10, marginBottom: 4 }}>
          {signal.suggested_entry && (
            <span style={{ color: 'var(--text-secondary)' }}>
              Entry: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>${signal.suggested_entry.toFixed(2)}</span>
            </span>
          )}
          {signal.target_price && (
            <span style={{ color: 'var(--text-secondary)' }}>
              Target: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-buy)' }}>${signal.target_price.toFixed(2)}</span>
            </span>
          )}
          {signal.stop_loss && (
            <span style={{ color: 'var(--text-secondary)' }}>
              Stop: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-sell)' }}>${signal.stop_loss.toFixed(2)}</span>
            </span>
          )}
        </div>
      )}

      {/* Key factors */}
      {signal.key_factors.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
          {signal.key_factors.slice(0, 3).map((f, i) => (
            <span
              key={i}
              style={{
                fontSize: 9,
                padding: '1px 6px',
                background: 'var(--bg-panel-header)',
                color: 'var(--text-secondary)',
                borderRadius: 3,
                border: '1px solid var(--border-subtle)',
              }}
            >
              {f.length > 40 ? f.slice(0, 40) + '…' : f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
