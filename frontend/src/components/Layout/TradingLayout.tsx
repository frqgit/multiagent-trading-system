// ── Draggable / resizable grid layout (IRESS ViewPoint style) ──

import React, { useState, useCallback, useMemo } from 'react';
import { Responsive, WidthProvider, type Layout, type Layouts } from 'react-grid-layout';
import { Watchlist } from '../Watchlist/Watchlist';
import { CandlestickChart } from '../Chart/CandlestickChart';
import { OrderBookPanel } from '../OrderBook/OrderBook';
import { AISignals } from '../Signals/AISignals';
import { Portfolio } from '../Portfolio/Portfolio';

const ResponsiveGridLayout = WidthProvider(Responsive);

const DEFAULT_LAYOUTS: Layouts = {
  lg: [
    { i: 'watchlist', x: 0, y: 0, w: 3, h: 12, minW: 2, minH: 6 },
    { i: 'chart', x: 3, y: 0, w: 6, h: 12, minW: 4, minH: 6 },
    { i: 'orderbook', x: 9, y: 0, w: 3, h: 12, minW: 2, minH: 6 },
    { i: 'signals', x: 0, y: 12, w: 4, h: 10, minW: 3, minH: 5 },
    { i: 'portfolio', x: 4, y: 12, w: 8, h: 10, minW: 4, minH: 5 },
  ],
  md: [
    { i: 'watchlist', x: 0, y: 0, w: 3, h: 10, minW: 2, minH: 5 },
    { i: 'chart', x: 3, y: 0, w: 7, h: 10, minW: 4, minH: 5 },
    { i: 'orderbook', x: 0, y: 10, w: 3, h: 8, minW: 2, minH: 5 },
    { i: 'signals', x: 3, y: 10, w: 4, h: 8, minW: 3, minH: 5 },
    { i: 'portfolio', x: 7, y: 10, w: 3, h: 8, minW: 3, minH: 5 },
  ],
  sm: [
    { i: 'watchlist', x: 0, y: 0, w: 6, h: 8, minW: 3, minH: 5 },
    { i: 'chart', x: 0, y: 8, w: 6, h: 10, minW: 4, minH: 6 },
    { i: 'orderbook', x: 0, y: 18, w: 6, h: 8, minW: 3, minH: 5 },
    { i: 'signals', x: 0, y: 26, w: 6, h: 8, minW: 3, minH: 5 },
    { i: 'portfolio', x: 0, y: 34, w: 6, h: 8, minW: 3, minH: 5 },
  ],
};

const PANEL_MAP: Record<string, React.FC> = {
  watchlist: Watchlist,
  chart: CandlestickChart,
  orderbook: OrderBookPanel,
  signals: AISignals,
  portfolio: Portfolio,
};

export const TradingLayout: React.FC = () => {
  const [layouts, setLayouts] = useState<Layouts>(DEFAULT_LAYOUTS);

  const onLayoutChange = useCallback((_: Layout[], allLayouts: Layouts) => {
    setLayouts(allLayouts);
  }, []);

  const panels = useMemo(
    () =>
      Object.entries(PANEL_MAP).map(([id, Component]) => (
        <div key={id} style={{ overflow: 'hidden' }}>
          <Component />
        </div>
      )),
    []
  );

  return (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        background: 'var(--bg-primary)',
        padding: '4px',
      }}
    >
      <ResponsiveGridLayout
        className="react-grid-layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 900, sm: 600 }}
        cols={{ lg: 12, md: 10, sm: 6 }}
        rowHeight={30}
        margin={[4, 4]}
        containerPadding={[0, 0]}
        onLayoutChange={onLayoutChange}
        draggableHandle=".panel-drag-handle"
        compactType="vertical"
        isResizable
        isDraggable
        useCSSTransforms
      >
        {panels}
      </ResponsiveGridLayout>
    </div>
  );
};
