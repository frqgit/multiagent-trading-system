// ── Header bar with branding, symbol search, connection status ──

import React from 'react';
import { useStore } from '../../store';
import { SymbolSearch } from '../Search/SymbolSearch';

export const Header: React.FC = () => {
  const wsConnected = useStore((s) => s.wsConnected);
  const activeSymbol = useStore((s) => s.activeSymbol);
  const marketData = useStore((s) => s.marketData[s.activeSymbol]);

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 42,
        padding: '0 16px',
        background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border-primary)',
        flexShrink: 0,
      }}
    >
      {/* Left: Branding */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: 4,
              background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              fontWeight: 700,
              color: '#fff',
            }}
          >
            TE
          </div>
          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-bright)' }}>
            TradingEdge
          </span>
          <span
            style={{
              fontSize: 10,
              color: 'var(--accent-cyan)',
              fontWeight: 500,
              padding: '1px 6px',
              border: '1px solid var(--accent-cyan)',
              borderRadius: 3,
              opacity: 0.8,
            }}
          >
            AI
          </span>
        </div>

        {/* Active symbol quick info */}
        {marketData && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginLeft: 8 }}>
            <span style={{ fontWeight: 600, color: 'var(--text-bright)', fontFamily: 'var(--font-mono)' }}>
              {activeSymbol}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                fontSize: 14,
                color: 'var(--text-bright)',
              }}
            >
              ${marketData.current_price.toFixed(2)}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 500,
                fontSize: 12,
                color: marketData.price_change >= 0 ? 'var(--color-buy)' : 'var(--color-sell)',
              }}
            >
              {marketData.price_change >= 0 ? '+' : ''}
              {marketData.price_change.toFixed(2)} ({marketData.price_change_pct.toFixed(2)}%)
            </span>
          </div>
        )}
      </div>

      {/* Center: Search */}
      <SymbolSearch />

      {/* Right: Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 11,
            color: wsConnected ? 'var(--color-buy)' : 'var(--text-muted)',
          }}
        >
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: wsConnected ? 'var(--color-buy)' : 'var(--text-muted)',
              boxShadow: wsConnected ? '0 0 6px var(--color-buy)' : 'none',
            }}
          />
          {wsConnected ? 'LIVE' : 'OFFLINE'}
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {new Date().toLocaleTimeString()}
        </span>
      </div>
    </header>
  );
};
