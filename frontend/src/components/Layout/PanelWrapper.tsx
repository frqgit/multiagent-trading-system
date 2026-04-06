// ── Panel wrapper with drag handle + header ──

import React from 'react';

interface Props {
  title: string;
  icon?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const PanelWrapper: React.FC<Props> = ({ title, icon, children, actions, className = '' }) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
      boxShadow: 'var(--shadow-panel)',
    }}
    className={className}
  >
    {/* Drag handle header */}
    <div
      className="panel-drag-handle"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        background: 'var(--bg-panel-header)',
        borderBottom: '1px solid var(--border-primary)',
        cursor: 'grab',
        userSelect: 'none',
        minHeight: 32,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {icon && <span style={{ fontSize: 14 }}>{icon}</span>}
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
            color: 'var(--text-secondary)',
          }}
        >
          {title}
        </span>
      </div>
      {actions && <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>{actions}</div>}
    </div>
    {/* Content */}
    <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>{children}</div>
  </div>
);
