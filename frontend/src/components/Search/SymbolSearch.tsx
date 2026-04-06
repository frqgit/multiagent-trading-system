// ── Fast symbol search with keyboard navigation ──

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useStore } from '../../store';

const POPULAR_SYMBOLS = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'WMT',
  'BHP.AX', 'CBA.AX', 'CSL.AX', 'WES.AX', 'NAB.AX', 'ANZ.AX', 'FMG.AX', 'RIO.AX',
  'NFLX', 'AMD', 'INTC', 'DIS', 'PYPL', 'BA', 'GS', 'UBER', 'SQ', 'COIN',
];

export const SymbolSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const setActiveSymbol = useStore((s) => s.setActiveSymbol);
  const addToWatchlist = useStore((s) => s.addToWatchlist);

  const filtered = query.trim()
    ? POPULAR_SYMBOLS.filter((s) => s.toLowerCase().includes(query.toLowerCase())).slice(0, 10)
    : POPULAR_SYMBOLS.slice(0, 10);

  const select = useCallback(
    (sym: string) => {
      setActiveSymbol(sym);
      addToWatchlist(sym);
      setQuery('');
      setOpen(false);
      inputRef.current?.blur();
    },
    [setActiveSymbol, addToWatchlist]
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (query.trim() && filtered.length === 0) {
        select(query.trim().toUpperCase());
      } else if (filtered[selectedIdx]) {
        select(filtered[selectedIdx]);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  // Global shortcut: Ctrl+K or /
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !(e.target instanceof HTMLInputElement))) {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div style={{ position: 'relative', width: 280 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'var(--bg-input)',
          border: `1px solid ${open ? 'var(--border-active)' : 'var(--border-primary)'}`,
          borderRadius: 'var(--radius-md)',
          padding: '4px 10px',
          transition: 'border-color 0.15s',
        }}
      >
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>⌕</span>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelectedIdx(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
          placeholder="Search symbol... (Ctrl+K)"
          style={{
            background: 'none',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            width: '100%',
          }}
        />
        <kbd
          style={{
            fontSize: 9,
            padding: '1px 4px',
            background: 'var(--bg-panel-header)',
            border: '1px solid var(--border-primary)',
            borderRadius: 3,
            color: 'var(--text-muted)',
          }}
        >
          /
        </kbd>
      </div>

      {open && filtered.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-dropdown)',
            zIndex: 1000,
            maxHeight: 300,
            overflow: 'auto',
          }}
        >
          {filtered.map((sym, i) => (
            <div
              key={sym}
              onMouseDown={() => select(sym)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 12px',
                cursor: 'pointer',
                background: i === selectedIdx ? 'var(--bg-hover)' : 'transparent',
                borderLeft: i === selectedIdx ? '2px solid var(--accent-blue)' : '2px solid transparent',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 600,
                  fontSize: 12,
                  color: 'var(--text-bright)',
                  minWidth: 70,
                }}
              >
                {sym}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
