// ── Watchlist panel with real-time price updates ──

import React from 'react';
import { PanelWrapper } from '../Layout/PanelWrapper';
import { useStore } from '../../store';

export const Watchlist: React.FC = () => {
  const watchlist = useStore((s) => s.watchlist);
  const activeSymbol = useStore((s) => s.activeSymbol);
  const setActiveSymbol = useStore((s) => s.setActiveSymbol);
  const removeFromWatchlist = useStore((s) => s.removeFromWatchlist);

  return (
    <PanelWrapper title="Watchlist" icon="📋">
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
        }}
      >
        <thead>
          <tr
            style={{
              background: 'var(--bg-panel-header)',
              position: 'sticky',
              top: 0,
              zIndex: 1,
            }}
          >
            {['Symbol', 'Last', 'Chg', 'Chg%', 'Vol'].map((h) => (
              <th
                key={h}
                style={{
                  padding: '5px 8px',
                  textAlign: h === 'Symbol' ? 'left' : 'right',
                  fontWeight: 500,
                  color: 'var(--text-muted)',
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  borderBottom: '1px solid var(--border-primary)',
                }}
              >
                {h}
              </th>
            ))}
            <th style={{ width: 24, borderBottom: '1px solid var(--border-primary)' }} />
          </tr>
        </thead>
        <tbody>
          {watchlist.map((item) => {
            const isActive = item.symbol === activeSymbol;
            const isPositive = item.price_change >= 0;
            const color = item.current_price === 0
              ? 'var(--text-muted)'
              : isPositive
              ? 'var(--color-buy)'
              : 'var(--color-sell)';

            return (
              <tr
                key={item.symbol}
                onClick={() => setActiveSymbol(item.symbol)}
                style={{
                  cursor: 'pointer',
                  background: isActive ? 'var(--bg-hover)' : 'transparent',
                  borderLeft: isActive ? '2px solid var(--accent-blue)' : '2px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent';
                }}
              >
                <td
                  style={{
                    padding: '5px 8px',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 600,
                    color: isActive ? 'var(--accent-blue)' : 'var(--text-bright)',
                    fontSize: 11,
                  }}
                >
                  {item.symbol}
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>
                    {item.company_name}
                  </div>
                </td>
                <td
                  style={{
                    padding: '5px 8px',
                    textAlign: 'right',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 500,
                    color: 'var(--text-bright)',
                  }}
                >
                  {item.current_price > 0 ? `$${item.current_price.toFixed(2)}` : '—'}
                </td>
                <td style={{ padding: '5px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color }}>
                  {item.current_price > 0 ? `${isPositive ? '+' : ''}${item.price_change.toFixed(2)}` : '—'}
                </td>
                <td style={{ padding: '5px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color, fontWeight: 500 }}>
                  {item.current_price > 0 ? `${isPositive ? '+' : ''}${item.price_change_pct.toFixed(2)}%` : '—'}
                </td>
                <td
                  style={{
                    padding: '5px 8px',
                    textAlign: 'right',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-secondary)',
                    fontSize: 11,
                  }}
                >
                  {item.volume > 0 ? formatVolume(item.volume) : '—'}
                </td>
                <td style={{ padding: '5px 4px', textAlign: 'center' }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFromWatchlist(item.symbol);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      fontSize: 12,
                      opacity: 0.5,
                      padding: 2,
                    }}
                    title="Remove"
                  >
                    ×
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </PanelWrapper>
  );
};

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toString();
}
