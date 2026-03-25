import { CSSProperties } from 'react';

interface StatsCardProps {
  label: string;
  value: number | string;
  accent: string;
  icon: string;
  subtitle?: string;
}

export default function StatsCard({ label, value, accent, icon, subtitle }: StatsCardProps) {
  const style: CSSProperties = {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    padding: '20px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: 16,
    minWidth: 0,
  };

  const iconStyle: CSSProperties = {
    width: 40,
    height: 40,
    borderRadius: 8,
    background: `${accent}18`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 18,
    flexShrink: 0,
  };

  const valueStyle: CSSProperties = {
    fontFamily: 'var(--font-mono)',
    fontSize: 28,
    fontWeight: 600,
    color: accent,
    lineHeight: 1,
    marginBottom: 4,
  };

  const labelStyle: CSSProperties = {
    fontSize: 12,
    color: 'var(--text-secondary)',
    fontWeight: 500,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  };

  const subtitleStyle: CSSProperties = {
    fontSize: 11,
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)',
    marginTop: 4,
    opacity: 0.7,
  };

  return (
    <div style={style}>
      <div style={iconStyle}>{icon}</div>
      <div>
        <div style={valueStyle}>{typeof value === 'number' ? value.toLocaleString() : value}</div>
        <div style={labelStyle}>{label}</div>
        {subtitle && <div style={subtitleStyle}>{subtitle}</div>}
      </div>
    </div>
  );
}
