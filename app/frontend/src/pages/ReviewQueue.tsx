import { useEffect, useState } from 'react';
import { api, SyncStatus } from '../api';

interface SenderGroupData {
  sender_email: string;
  count: number;
  oldest: string;
  newest: string;
  email_ids: string[];
  sample_emails: Array<{ id: string; subject: string; snippet: string; date: string }>;
}

interface ReviewResponse {
  groups: SenderGroupData[];
  total_groups: number;
  total_emails: number;
  page: number;
  page_size: number;
}

const btnBase = {
  padding: '4px 12px', borderRadius: 4, border: 'none', fontSize: 11,
  fontWeight: 600 as const, fontFamily: 'var(--font-mono)', textTransform: 'uppercase' as const,
  letterSpacing: '0.3px', cursor: 'pointer' as const,
};

export default function ReviewQueue() {
  const [data, setData] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<'count' | 'sender'>('count');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);

  const load = async (p = page, sort = sortBy) => {
    setLoading(true);
    try {
      const r = await fetch(`/api/emails/review/groups?page=${p}&page_size=20&sort=${sort}`);
      const d: ReviewResponse = await r.json();
      setData(d);
      setPage(p);
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    load(1, sortBy);
    api.getSyncStatus().then(setSyncStatus).catch(() => {});
  }, [sortBy]);

  const handleClassify = async (ids: string[], classification: string) => {
    await api.bulkClassify(ids, classification);
    load();
  };

  const toggleExpand = (sender: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(sender) ? next.delete(sender) : next.add(sender);
      return next;
    });
  };

  const totalPages = data ? Math.ceil(data.total_groups / data.page_size) : 0;

  return (
    <div>
      <div className="page-header">
        <h2>Review Queue</h2>
        <p>
          {data ? `${data.total_emails.toLocaleString()} unclassified emails from ${data.total_groups.toLocaleString()} senders` : 'Loading...'}
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, fontSize: 12 }}>
        <span style={{ color: 'var(--text-secondary)', padding: '4px 0' }}>Sort by:</span>
        {(['count', 'sender'] as const).map(s => (
          <button
            key={s}
            onClick={() => setSortBy(s)}
            style={{
              padding: '4px 10px', borderRadius: 4, border: '1px solid var(--border)',
              background: sortBy === s ? 'rgba(99,102,241,0.12)' : 'transparent',
              color: sortBy === s ? 'var(--primary)' : 'var(--text-secondary)',
              fontSize: 12, cursor: 'pointer',
            }}
          >
            {s === 'count' ? 'Email count' : 'Sender name'}
          </button>
        ))}
      </div>

      {syncStatus?.is_syncing && (
        <div style={{
          padding: '10px 16px', marginBottom: 16, borderRadius: 6, fontSize: 12,
          background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
          color: 'var(--warning)',
        }}>
          Sync in progress — Gmail deletions (archive/junk) are deferred until sync completes to avoid API contention.
        </div>
      )}

      {loading && <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>}

      {!loading && data && data.groups.length === 0 && (
        <div style={{
          padding: 60, textAlign: 'center', color: 'var(--text-secondary)',
          background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8,
        }}>
          All caught up! No unclassified emails.
        </div>
      )}

      {!loading && data && data.groups.map(group => (
        <div key={group.sender_email} style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 8, marginBottom: 8, overflow: 'hidden',
        }}>
          {/* Group header */}
          <div
            onClick={() => toggleExpand(group.sender_email)}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px', cursor: 'pointer', transition: 'background 0.1s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.02)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', width: 16 }}>
                {expanded.has(group.sender_email) ? '\u25BC' : '\u25B6'}
              </span>
              <span style={{ fontWeight: 500 }}>{group.sender_email}</span>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)',
                background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: 4,
              }}>
                {group.count.toLocaleString()}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6 }} onClick={e => e.stopPropagation()}>
              <button
                style={{ ...btnBase, background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}
                onClick={() => handleClassify(group.email_ids, 'archive')}
              >Archive</button>
              <button
                style={{ ...btnBase, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}
                onClick={() => handleClassify(group.email_ids, 'keep')}
              >Keep</button>
              <button
                style={{ ...btnBase, background: 'rgba(244,63,94,0.15)', color: '#f43f5e' }}
                onClick={() => handleClassify(group.email_ids, 'junk')}
              >Junk</button>
            </div>
          </div>

          {/* Expanded sample emails */}
          {expanded.has(group.sender_email) && group.sample_emails.map(email => (
            <div key={email.id} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '8px 16px 8px 44px', borderTop: '1px solid var(--border)', fontSize: 13,
            }}>
              <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {email.subject}
                <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>
                  {email.snippet ? ` — ${email.snippet.slice(0, 60)}` : ''}
                </span>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                {new Date(email.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
            </div>
          ))}
          {expanded.has(group.sender_email) && group.count > 5 && (
            <div style={{
              padding: '6px 44px', borderTop: '1px solid var(--border)',
              fontSize: 11, color: 'var(--text-secondary)',
            }}>
              ... and {group.count - 5} more
            </div>
          )}
        </div>
      ))}

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
          <span>{data.total_groups} sender groups</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              disabled={page <= 1}
              onClick={() => load(page - 1)}
              style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: page <= 1 ? 'default' : 'pointer', opacity: page <= 1 ? 0.4 : 1 }}
            >Prev</button>
            <span style={{ fontFamily: 'var(--font-mono)', padding: '4px 8px' }}>{page} / {totalPages}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => load(page + 1)}
              style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: page >= totalPages ? 'default' : 'pointer', opacity: page >= totalPages ? 0.4 : 1 }}
            >Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
