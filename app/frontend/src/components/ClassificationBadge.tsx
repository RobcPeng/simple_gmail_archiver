import { CSSProperties } from 'react';

interface ClassificationBadgeProps {
  classification: string | null;
}

const colors: Record<string, { bg: string; text: string }> = {
  archive: { bg: 'rgba(99, 102, 241, 0.15)', text: '#818cf8' },
  keep: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981' },
  junk: { bg: 'rgba(244, 63, 94, 0.15)', text: '#f43f5e' },
  unclassified: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b' },
};

export default function ClassificationBadge({ classification }: ClassificationBadgeProps) {
  const label = classification || 'unclassified';
  const c = colors[label] || colors.unclassified;

  const style: CSSProperties = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    background: c.bg,
    color: c.text,
    whiteSpace: 'nowrap',
  };

  return <span style={style}>{label}</span>;
}
