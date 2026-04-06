// ── Order Book depth panel with bid/ask visualization ──

import React, { useMemo } from 'react';
import { PanelWrapper } from '../Layout/PanelWrapper';
import { useStore } from '../../store';

export const OrderBookPanel: React.FC = () => {
  const orderBook = useStore((s) => s.orderBook);
  const activeSymbol = useStore((s) => s.activeSymbol);

  const maxTotal = useMemo(() => {
    const maxBid = orderBook.bids.length > 0 ? orderBook.bids[orderBook.bids.length - 1].total : 1;
    const maxAsk = orderBook.asks.length > 0 ? orderBook.asks[orderBook.asks.length - 1].total : 1;
    return Math.max(maxBid, maxAsk);
  }, [orderBook]);

  return (
    <PanelWrapper
      title="Order Book"
      icon="📊"
      actions={
        <div style={{ display: 'flex', gap: 8, fontSize: 10 }}>
          <span style={{ color: 'var(--text-muted)' }}>
            Spread:{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {orderBook.spread.toFixed(2)} ({orderBook.spreadPct.toFixed(3)}%)
            </span>
          </span>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontSize: 11 }}>
        {/* Column headers */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            padding: '4px 10px',
            fontSize: 9,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: 'var(--text-muted)',
            fontWeight: 600,
            borderBottom: '1px solid var(--border-primary)',
          }}
        >
          <span>Price</span>
          <span style={{ textAlign: 'right' }}>Qty</span>
          <span style={{ textAlign: 'right' }}>Total</span>
        </div>

        {/* Asks (reversed — highest first, closest to spread at bottom) */}
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column-reverse' }}>
          {orderBook.asks.slice(0, 12).map((level, i) => (
            <div
              key={`ask-${i}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                padding: '2px 10px',
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  bottom: 0,
                  width: `${(level.total / maxTotal) * 100}%`,
                  background: 'rgba(239, 68, 68, 0.06)',
                  borderRight: '1px solid rgba(239, 68, 68, 0.15)',
                }}
              />
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-sell)', fontWeight: 500, zIndex: 1 }}>
                {level.price.toFixed(2)}
              </span>
              <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', zIndex: 1 }}>
                {level.quantity.toLocaleString()}
              </span>
              <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', zIndex: 1 }}>
                {level.total.toLocaleString()}
              </span>
            </div>
          ))}
        </div>

        {/* Spread bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '6px 10px',
            borderTop: '1px solid var(--border-primary)',
            borderBottom: '1px solid var(--border-primary)',
            background: 'var(--bg-panel-header)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: 14,
              color: 'var(--text-bright)',
            }}
          >
            {orderBook.lastPrice.toFixed(2)}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 8 }}>{activeSymbol}</span>
        </div>

        {/* Bids */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {orderBook.bids.slice(0, 12).map((level, i) => (
            <div
              key={`bid-${i}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                padding: '2px 10px',
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  bottom: 0,
                  width: `${(level.total / maxTotal) * 100}%`,
                  background: 'rgba(34, 197, 94, 0.06)',
                  borderRight: '1px solid rgba(34, 197, 94, 0.15)',
                }}
              />
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-buy)', fontWeight: 500, zIndex: 1 }}>
                {level.price.toFixed(2)}
              </span>
              <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', zIndex: 1 }}>
                {level.quantity.toLocaleString()}
              </span>
              <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', zIndex: 1 }}>
                {level.total.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </PanelWrapper>
  );
};
