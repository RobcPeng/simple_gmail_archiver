import { CSSProperties } from 'react';
import ClassificationBadge from './ClassificationBadge';
import type { Email } from '../api';

interface EmailRowProps {
  email: Email;
  selected: boolean;
  onToggle: (id: string) => void;
}

const rowStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '32px 180px 1fr 100px 120px 40px',
  gap: 12,
  alignItems: 'center',
  padding: '10px 16px',
  borderBottom: '1px solid var(--border)',
  fontSize: 13,
  transition: 'background 0.1s',
};

const senderStyle: CSSProperties = {
  fontWeight: 500,
  color: 'var(--text-primary)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const subjectStyle: CSSProperties = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const snippetStyle: CSSProperties = {
  color: 'var(--text-secondary)',
  marginLeft: 6,
};

const dateStyle: CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 11,
  color: 'var(--text-secondary)',
  textAlign: 'right',
};

export default function EmailRow({ email, selected, onToggle }: EmailRowProps) {
  const d = new Date(email.date);
  const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <div
      style={{ ...rowStyle, background: selected ? 'rgba(99,102,241,0.08)' : 'transparent' }}
      onMouseEnter={(e) => {
        if (!selected) (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.02)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = selected ? 'rgba(99,102,241,0.08)' : 'transparent';
      }}
    >
      <div>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(email.id)}
          style={{ accentColor: 'var(--primary)' }}
        />
      </div>
      <div style={senderStyle} title={email.sender_email}>
        {email.sender || email.sender_email}
      </div>
      <div style={subjectStyle}>
        {email.subject}
        <span style={snippetStyle}>{email.snippet ? ` - ${email.snippet}` : ''}</span>
      </div>
      <div>
        <ClassificationBadge classification={email.classification} />
      </div>
      <div style={dateStyle}>{dateStr}</div>
      <div>
        {email.eml_path && (
          <a
            href={`/api/emails/${email.id}/download`}
            title="Download .eml"
            style={{ fontSize: 14, color: 'var(--text-secondary)' }}
          >
            &#8615;
          </a>
        )}
      </div>
    </div>
  );
}
