// ── App root — connects WebSockets and renders layout ──

import React, { useEffect, useRef } from 'react';
import { Header } from './components/Header/Header';
import { TradingLayout } from './components/Layout/TradingLayout';
import { useStore } from './store';
import { marketWS, signalsWS, portfolioWS } from './services/websocket';
import type { MarketData } from './types/market';

export const App: React.FC = () => {
  const updateMarketData = useStore((s) => s.updateMarketData);
  const addSignal = useStore((s) => s.addSignal);
  const updatePortfolio = useStore((s) => s.updatePortfolio);
  const setWsConnected = useStore((s) => s.setWsConnected);
  const watchlist = useStore((s) => s.watchlist);
  const activeSymbol = useStore((s) => s.activeSymbol);
  const subscribedRef = useRef(false);

  // Connect WebSockets on mount
  useEffect(() => {
    marketWS.connect();
    signalsWS.connect();
    portfolioWS.connect();

    const unsub1 = marketWS.on('_connected', () => {
      setWsConnected(true);
      // Subscribe to all watchlist symbols
      const symbols = watchlist.map((w) => w.symbol);
      if (symbols.length > 0) {
        marketWS.send({ subscribe: symbols });
        subscribedRef.current = true;
      }
    });

    const unsub2 = marketWS.on('_disconnected', () => {
      setWsConnected(false);
      subscribedRef.current = false;
    });

    const unsub3 = marketWS.on('market_data', (msg) => {
      const sym = msg.symbol as string;
      const data = msg.data as MarketData;
      if (sym && data) {
        updateMarketData(sym, data);
      }
    });

    const unsub4 = signalsWS.on('ai_signal', (msg) => {
      const data = msg.data as Record<string, unknown>;
      if (data) {
        addSignal({
          symbol: (msg.symbol as string) || '',
          action: (data.action as 'HOLD') || 'HOLD',
          confidence: (data.confidence as number) || 0,
          reasoning: (data.reasoning as string) || '',
          key_factors: (data.key_factors as string[]) || [],
          suggested_entry: (data.suggested_entry as number) || null,
          target_price: (data.target_price as number) || null,
          stop_loss: (data.stop_loss as number) || null,
          time_horizon: (data.time_horizon as string) || null,
          timestamp: new Date().toISOString(),
        });
      }
    });

    const unsub5 = portfolioWS.on('portfolio_update', (msg) => {
      const data = msg.data as Record<string, unknown>;
      if (data) updatePortfolio(data);
    });

    return () => {
      unsub1();
      unsub2();
      unsub3();
      unsub4();
      unsub5();
      marketWS.disconnect();
      signalsWS.disconnect();
      portfolioWS.disconnect();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-subscribe when watchlist changes
  useEffect(() => {
    if (subscribedRef.current) {
      const symbols = watchlist.map((w) => w.symbol);
      marketWS.send({ subscribe: symbols });
    }
  }, [watchlist]);

  // Subscribe signals to active symbol
  useEffect(() => {
    if (activeSymbol) {
      signalsWS.send({ symbol: activeSymbol });
    }
  }, [activeSymbol]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Header />
      <TradingLayout />
    </div>
  );
};
