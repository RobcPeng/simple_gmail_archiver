import { useState, CSSProperties } from 'react';
import ClassificationBadge from './ClassificationBadge';
import type { Email } from '../api';

interface SenderGroupProps {
  senderEmail: string;
  emails: Email[];
  onClassifyAll: (ids: string[], classification: string) => void;
}

const groupStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  marginBottom: 8,
  overflow: 'hidden',
};

const headerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 16px',
  cursor: 'pointer',
  transition: 'background 0.1s',
};

const btnBase: CSSProperties = {
  padding: '4px 12px',
  borderRadius: 4,
  border: 'none',
  fontSize: 11,
  fontWeight: 600,
  fontFamily: 'var(--font-mono)',
  textTransform: 'uppercase',
  letterSpacing: '0.3px',
  cursor: 'pointer',
};

const emailItemStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '8px 16px 8px 32px',
  borderTop: '1px solid var(--border)',
  fontSize: 13,
};

export default function SenderGroup({ senderEmail, emails, onClassifyAll }: SenderGroupProps) {
  const [expanded, setExpanded] = useState(false);
  const ids = emails.map((e) => e.id);

  return (
    <div style={groupStyle}>
      <div
        style={headerStyle}
        onClick={() => setExpanded(!expanded)}
        onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.02)'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', width: 16 }}>
            {expanded ? '\u25BC' : '\u25B6'}
          </span>
          <span style={{ fontWeight: 500 }}>{senderEmail}</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-secondary)',
              background: 'rgba(255,255,255,0.06)',
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            {emails.length}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
          <button
            style={{ ...btnBase, background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}
            onClick={() => onClassifyAll(ids, 'archive')}
          >
            Archive
          </button>
          <button
            style={{ ...btnBase, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}
            onClick={() => onClassifyAll(ids, 'keep')}
          >
            Keep
          </button>
          <button
            style={{ ...btnBase, background: 'rgba(244,63,94,0.15)', color: '#f43f5e' }}
            onClick={() => onClassifyAll(ids, 'junk')}
          >
            Junk
          </button>
        </div>
      </div>
      {expanded &&
        emails.map((email) => (
          <div key={email.id} style={emailItemStyle}>
            <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {email.subject}
            </div>
            <ClassificationBadge classification={email.classification} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
              {new Date(email.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          </div>
        ))}
    </div>
  );
}
