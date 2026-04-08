// ── Advanced candlestick chart with lightweight-charts ──

import { store } from '../store.js';
import { calcSMA } from '../utils.js';

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1D', '1W', '1M'];
const INDICATORS = ['Volume', 'MA20', 'MA50'];

let chartInstance = null;
let candleSeries = null;
let volumeSeries = null;
let ma20Series = null;
let ma50Series = null;
let resizeObserver = null;
const activeIndicators = new Set(['Volume', 'MA20', 'MA50']);

export function initChart() {
  const titleEl = document.getElementById('chart-title');
  const actionsEl = document.getElementById('chart-actions');
  const bodyEl = document.getElementById('chart-body');

  // Overlay for RSI/MACD readouts
  const overlay = document.createElement('div');
  overlay.className = 'chart-overlay';
  overlay.id = 'chart-overlay';
  bodyEl.appendChild(overlay);

  // Chart container
  const container = document.createElement('div');
  container.className = 'chart-container';
  container.id = 'chart-canvas';
  bodyEl.appendChild(container);

  // Render action buttons
  renderActions(actionsEl);

  // Event delegation for buttons — attached once
  actionsEl.addEventListener('click', (e) => {
    const indBtn = e.target.closest('[data-indicator]');
    if (indBtn) {
      const ind = indBtn.dataset.indicator;
      if (activeIndicators.has(ind)) activeIndicators.delete(ind);
      else activeIndicators.add(ind);
      renderActions(actionsEl);
      buildChart(container);
      return;
    }
    const tfBtn = e.target.closest('[data-tf]');
    if (tfBtn) {
      store.setTimeframe(tfBtn.dataset.tf);
      renderActions(actionsEl);
    }
  });

  // Build chart
  buildChart(container);

  // Store subscriptions
  store.on('activeSymbol', () => {
    updateTitle(titleEl);
    populateData();
    updateOverlay(overlay);
  });
  store.on('timeframe', () => {
    updateTitle(titleEl);
  });
  store.on('marketData', () => {
    populateData();
    updateOverlay(overlay);
  });

  updateTitle(titleEl);
  updateOverlay(overlay);
}

function renderActions(el) {
  const tf = store.get('timeframe');
  let html = '';
  INDICATORS.forEach(ind => {
    html += `<button class="chart-btn${activeIndicators.has(ind) ? ' active' : ''}" data-indicator="${ind}">${ind}</button>`;
  });
  html += '<div class="chart-divider"></div>';
  TIMEFRAMES.forEach(t => {
    html += `<button class="chart-tf-btn${t === tf ? ' active' : ''}" data-tf="${t}">${t}</button>`;
  });
  el.innerHTML = html;
}

function buildChart(container) {
  if (chartInstance) {
    chartInstance.remove();
    chartInstance = null;
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }

  if (typeof LightweightCharts === 'undefined') {
    container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">Loading chart library…</div>';
    return;
  }

  const { createChart, ColorType, CrosshairMode } = LightweightCharts;

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
      borderColor: '#1e293b',
      scaleMargins: { top: 0.1, bottom: activeIndicators.has('Volume') ? 0.25 : 0.05 },
    },
    timeScale: {
      borderColor: '#1e293b',
      timeVisible: true,
      secondsVisible: false,
    },
  });

  chartInstance = chart;

  // Candlestick series
  candleSeries = chart.addCandlestickSeries({
    upColor: '#22c55e',
    downColor: '#ef4444',
    borderUpColor: '#22c55e',
    borderDownColor: '#ef4444',
    wickUpColor: '#22c55e',
    wickDownColor: '#ef4444',
  });

  // Volume histogram
  volumeSeries = null;
  if (activeIndicators.has('Volume')) {
    volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
  }

  // Moving averages
  ma20Series = null;
  if (activeIndicators.has('MA20')) {
    ma20Series = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  ma50Series = null;
  if (activeIndicators.has('MA50')) {
    ma50Series = chart.addLineSeries({
      color: '#8b5cf6',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  populateData();

  // Auto-resize
  resizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) {
      chart.applyOptions({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    }
  });
  resizeObserver.observe(container);
}

function populateData() {
  const sym = store.get('activeSymbol');
  const md = store.get('marketData')[sym];
  if (!md?.price_history_30d?.length || !candleSeries) return;

  const candles = md.price_history_30d.map(p => ({
    time: p.date,
    open: p.open ?? p.close * (1 + (Math.random() - 0.5) * 0.02),
    high: p.high ?? p.close * (1 + Math.random() * 0.015),
    low: p.low ?? p.close * (1 - Math.random() * 0.015),
    close: p.close,
  }));

  candleSeries.setData(candles);

  if (volumeSeries) {
    const volData = candles.map(c => ({
      time: c.time,
      value: md.price_history_30d.find(p => p.date === c.time)?.volume ?? Math.random() * 50000000,
      color: c.close >= c.open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)',
    }));
    volumeSeries.setData(volData);
  }

  if (ma20Series && candles.length >= 20) {
    ma20Series.setData(calcSMA(candles.map(c => ({ time: c.time, value: c.close })), 20));
  }

  if (ma50Series && candles.length >= 50) {
    ma50Series.setData(calcSMA(candles.map(c => ({ time: c.time, value: c.close })), 50));
  }

  chartInstance?.timeScale().fitContent();
}

function updateTitle(el) {
  el.textContent = store.get('activeSymbol') + ' — ' + store.get('timeframe');
}

function updateOverlay(el) {
  const sym = store.get('activeSymbol');
  const md = store.get('marketData')[sym];
  if (!md) {
    el.innerHTML = '';
    return;
  }
  const rsiColor = md.rsi > 70 ? 'var(--color-sell)' : md.rsi < 30 ? 'var(--color-buy)' : 'var(--text-primary)';
  const macdColor = md.macd >= 0 ? 'var(--color-buy)' : 'var(--color-sell)';

  el.innerHTML =
    `<span style="color:var(--text-muted)">RSI(14): <span style="color:${rsiColor};font-family:var(--font-mono);font-weight:600">${md.rsi?.toFixed(1) ?? '—'}</span></span>` +
    `<span style="color:var(--text-muted)">MACD: <span style="color:${macdColor};font-family:var(--font-mono);font-weight:600">${md.macd?.toFixed(3) ?? '—'}</span></span>` +
    `<span style="color:var(--text-muted)">Signal: <span style="font-family:var(--font-mono);color:var(--text-secondary)">${md.macd_signal?.toFixed(3) ?? '—'}</span></span>`;
}
