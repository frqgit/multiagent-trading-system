// ── Portfolio panel with positions + P&L ──

import React from 'react';
import { PanelWrapper } from '../Layout/PanelWrapper';
import { useStore } from '../../store';

export const Portfolio: React.FC = () => {
  const portfolio = useStore((s) => s.portfolio);
  const setActiveSymbol = useStore((s) => s.setActiveSymbol);
  const { summary, positions, trade_statistics } = portfolio;

  const totalPnlColor =
    summary.unrealized_pnl > 0 ? 'var(--color-buy)' : summary.unrealized_pnl < 0 ? 'var(--color-sell)' : 'var(--text-secondary)';

  return (
    <PanelWrapper title="Portfolio" icon="💼">
      <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Summary cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 8,
          }}
        >
          <SummaryCard label="Total Value" value={`$${formatNumber(summary.total_value)}`} />
          <SummaryCard label="Cash" value={`$${formatNumber(summary.cash)}`} />
          <SummaryCard
            label="Unrealized P&L"
            value={`${summary.unrealized_pnl >= 0 ? '+' : ''}$${formatNumber(summary.unrealized_pnl)}`}
            color={totalPnlColor}
          />
        </div>

        {/* Trade stats */}
        <div
          style={{
            display: 'flex',
            gap: 16,
            padding: '6px 10px',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            fontSize: 10,
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>
            Win Rate:{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>
              {(trade_statistics.win_rate * 100).toFixed(1)}%
            </span>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            Trades:{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>
              {trade_statistics.total_trades}
            </span>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            Avg P&L:{' '}
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                color: trade_statistics.avg_pnl >= 0 ? 'var(--color-buy)' : 'var(--color-sell)',
              }}
            >
              ${trade_statistics.avg_pnl.toFixed(2)}
            </span>
          </span>
        </div>

        {/* Positions table */}
        {positions.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr>
                {['Symbol', 'Qty', 'Avg Cost', 'Mkt Value', 'P&L'].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: '4px 6px',
                      textAlign: h === 'Symbol' ? 'left' : 'right',
                      fontWeight: 500,
                      color: 'var(--text-muted)',
                      fontSize: 9,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      borderBottom: '1px solid var(--border-primary)',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => {
                const pnlColor = pos.unrealized_pnl >= 0 ? 'var(--color-buy)' : 'var(--color-sell)';
                return (
                  <tr
                    key={pos.symbol}
                    onClick={() => setActiveSymbol(pos.symbol)}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td
                      style={{
                        padding: '5px 6px',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 600,
                        color: 'var(--text-bright)',
                      }}
                    >
                      {pos.symbol}
                    </td>
                    <td style={{ padding: '5px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {pos.quantity}
                    </td>
                    <td style={{ padding: '5px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      ${pos.avg_cost.toFixed(2)}
                    </td>
                    <td style={{ padding: '5px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                      ${formatNumber(pos.market_value)}
                    </td>
                    <td style={{ padding: '5px 6px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: pnlColor }}>
                      {pos.unrealized_pnl >= 0 ? '+' : ''}${formatNumber(pos.unrealized_pnl)}
                      <div style={{ fontSize: 9, fontWeight: 400 }}>
                        {pos.unrealized_pnl_pct >= 0 ? '+' : ''}
                        {pos.unrealized_pnl_pct.toFixed(2)}%
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div
            style={{
              padding: 20,
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: 12,
            }}
          >
            <div style={{ fontSize: 20, marginBottom: 8 }}>💼</div>
            No open positions
          </div>
        )}
      </div>
    </PanelWrapper>
  );
};

const SummaryCard: React.FC<{ label: string; value: string; color?: string }> = ({
  label,
  value,
  color = 'var(--text-bright)',
}) => (
  <div
    style={{
      padding: '8px 10px',
      background: 'var(--bg-secondary)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-subtle)',
    }}
  >
    <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 2 }}>
      {label}
    </div>
    <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color }}>{value}</div>
  </div>
);

function formatNumber(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  return n.toFixed(2);
}
