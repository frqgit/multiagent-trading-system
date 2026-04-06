// ── Advanced candlestick chart with TradingView lightweight-charts ──

import React, { useEffect, useRef, useCallback, useState } from 'react';
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData as LWCandlestickData,
  type HistogramData,
  type Time,
} from 'lightweight-charts';
import { PanelWrapper } from '../Layout/PanelWrapper';
import { useStore } from '../../store';
import type { Timeframe } from '../../types/market';

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1D', '1W', '1M'];

// Indicator toggles
type Indicator = 'RSI' | 'MACD' | 'Volume' | 'MA20' | 'MA50' | 'EMA12' | 'EMA26';

export const CandlestickChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ma20Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const ma50Ref = useRef<ISeriesApi<'Line'> | null>(null);

  const activeSymbol = useStore((s) => s.activeSymbol);
  const timeframe = useStore((s) => s.timeframe);
  const setTimeframe = useStore((s) => s.setTimeframe);
  const marketData = useStore((s) => s.marketData[s.activeSymbol]);

  const [indicators, setIndicators] = useState<Set<Indicator>>(new Set(['Volume', 'MA20', 'MA50']));

  const toggleIndicator = (ind: Indicator) => {
    setIndicators((prev) => {
      const next = new Set(prev);
      if (next.has(ind)) next.delete(ind);
      else next.add(ind);
      return next;
    });
  };

  // Build chart
  const buildChart = useCallback(() => {
    if (!chartContainerRef.current) return;

    // Cleanup
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#131a2a' },
        textColor: '#94a3b8',
        fontSize: 11,
        fontFamily: "'Inter', sans-serif",
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
        horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(59, 130, 246, 0.4)', width: 1 },
        horzLine: { color: 'rgba(59, 130, 246, 0.4)', width: 1 },
      },
      rightPriceScale: {
        borderColor: 'var(--border-primary)',
        scaleMargins: { top: 0.1, bottom: indicators.has('Volume') ? 0.25 : 0.05 },
      },
      timeScale: {
        borderColor: 'var(--border-primary)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });
    candleSeriesRef.current = candleSeries;

    // Volume
    if (indicators.has('Volume')) {
      const volSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });
      volSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeriesRef.current = volSeries;
    }

    // MA lines
    if (indicators.has('MA20')) {
      ma20Ref.current = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (indicators.has('MA50')) {
      ma50Ref.current = chart.addLineSeries({
        color: '#8b5cf6',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // Populate with data
    if (marketData?.price_history_30d?.length) {
      const candles: LWCandlestickData[] = marketData.price_history_30d.map((p) => ({
        time: p.date as string,
        open: p.open ?? p.close * (1 + (Math.random() - 0.5) * 0.02),
        high: p.high ?? p.close * (1 + Math.random() * 0.015),
        low: p.low ?? p.close * (1 - Math.random() * 0.015),
        close: p.close,
      }));

      candleSeries.setData(candles as LWCandlestickData[]);

      // Volume data
      if (volumeSeriesRef.current) {
        const volData = candles.map((c) => ({
          time: c.time,
          value: marketData.price_history_30d.find((p) => p.date === c.time)?.volume ?? Math.random() * 50000000,
          color: c.close >= c.open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)',
        }));
        volumeSeriesRef.current.setData(volData as HistogramData[]);
      }

      // MA20
      if (ma20Ref.current && candles.length >= 20) {
        const maData = calcSMA(candles.map((c) => ({ time: c.time, value: c.close })), 20);
        ma20Ref.current.setData(maData);
      }

      // MA50
      if (ma50Ref.current && candles.length >= 50) {
        const maData = calcSMA(candles.map((c) => ({ time: c.time, value: c.close })), 50);
        ma50Ref.current.setData(maData);
      }

      chart.timeScale().fitContent();
    }

    // Resize observer
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [marketData, indicators]);

  useEffect(() => {
    const cleanup = buildChart();
    return () => cleanup?.();
  }, [buildChart]);

  return (
    <PanelWrapper
      title={`${activeSymbol} — ${timeframe}`}
      icon="📈"
      actions={
        <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {/* Indicator toggles */}
          {(['Volume', 'MA20', 'MA50'] as Indicator[]).map((ind) => (
            <button
              key={ind}
              onClick={() => toggleIndicator(ind)}
              style={{
                padding: '2px 6px',
                fontSize: 10,
                fontWeight: 500,
                background: indicators.has(ind) ? 'var(--accent-blue-dim)' : 'transparent',
                color: indicators.has(ind) ? 'var(--accent-blue)' : 'var(--text-muted)',
                border: `1px solid ${indicators.has(ind) ? 'var(--accent-blue)' : 'var(--border-primary)'}`,
                borderRadius: 3,
                cursor: 'pointer',
              }}
            >
              {ind}
            </button>
          ))}
          <div style={{ width: 1, height: 16, background: 'var(--border-primary)', margin: '0 4px' }} />
          {/* Timeframe selector */}
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              style={{
                padding: '2px 6px',
                fontSize: 10,
                fontWeight: 600,
                background: tf === timeframe ? 'var(--accent-blue)' : 'transparent',
                color: tf === timeframe ? '#fff' : 'var(--text-muted)',
                border: 'none',
                borderRadius: 3,
                cursor: 'pointer',
              }}
            >
              {tf}
            </button>
          ))}
        </div>
      }
    >
      {/* RSI sub-chart */}
      {marketData && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 12,
            zIndex: 10,
            display: 'flex',
            gap: 16,
            fontSize: 11,
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>
            RSI(14):{' '}
            <span
              style={{
                color:
                  marketData.rsi > 70
                    ? 'var(--color-sell)'
                    : marketData.rsi < 30
                    ? 'var(--color-buy)'
                    : 'var(--text-primary)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}
            >
              {marketData.rsi?.toFixed(1) ?? '—'}
            </span>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            MACD:{' '}
            <span
              style={{
                color: marketData.macd >= 0 ? 'var(--color-buy)' : 'var(--color-sell)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}
            >
              {marketData.macd?.toFixed(3) ?? '—'}
            </span>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            Signal:{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {marketData.macd_signal?.toFixed(3) ?? '—'}
            </span>
          </span>
        </div>
      )}
      <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
    </PanelWrapper>
  );
};

function calcSMA(
  data: { time: Time; value: number }[],
  period: number
): { time: Time; value: number }[] {
  const result: { time: Time; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].value;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}
