import { useEffect, useState, useRef } from 'react';
import StatsCard from '../components/StatsCard';
import { api, Stats, SyncStatus } from '../api';

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [maxMessages, setMaxMessages] = useState(100);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = () => {
    api.getStats().then(setStats).catch(() => {});
    api.getSyncStatus().then(setSync).catch(() => {});
  };

  useEffect(() => {
    refresh();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleSync = async (full: boolean) => {
    setSyncing(true);
    try {
      const params = full ? `full=true&max_messages=${maxMessages}` : '';
      await fetch(`/api/sync?${params}`, { method: 'POST' });
    } catch {}

    // Poll for completion
    pollRef.current = setInterval(() => {
      api.getSyncStatus().then((s) => {
        setSync(s);
        if (!s.is_syncing) {
          setSyncing(false);
          if (pollRef.current) clearInterval(pollRef.current);
          refresh();
        }
      });
      api.getStats().then(setStats);
    }, 2000);
  };

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of your email archive</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 28 }}>
        <StatsCard label="Total Synced" value={stats?.total_emails ?? 0} accent="var(--primary)" icon="&#9993;" subtitle={fmtSize(stats?.total_size_bytes ?? 0)} />
        <StatsCard label="Archived" value={stats?.classified_archive ?? 0} accent="var(--primary-hover)" icon="&#9745;" subtitle={fmtSize(stats?.classified_archive_size ?? 0)} />
        <StatsCard label="Keep" value={stats?.classified_keep ?? 0} accent="var(--success)" icon="&#10003;" subtitle={fmtSize(stats?.classified_keep_size ?? 0)} />
        <StatsCard label="Junk" value={stats?.classified_junk ?? 0} accent="var(--danger)" icon="&#10007;" subtitle={fmtSize(stats?.classified_junk_size ?? 0)} />
        <StatsCard label="Unclassified" value={stats?.unclassified ?? 0} accent="var(--warning)" icon="&#63;" subtitle={fmtSize(stats?.unclassified_size ?? 0)} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Sync</h3>
          {sync && (
            <div style={{ fontSize: 13 }}>
              <div style={{ color: sync.is_syncing ? 'var(--warning)' : 'var(--success)', marginBottom: 8 }}>
                {sync.is_syncing ? '● Syncing...' : '● Idle'}
              </div>
              <div style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>
                Account: {sync.account_email || 'Not connected'}
              </div>
              <div style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>
                Last sync: {sync.last_full_sync || 'Never'}
              </div>
              <div style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>
                Messages synced: <span style={{ fontFamily: 'var(--font-mono)' }}>{sync.synced_messages}</span>
              </div>

              {/* Max messages input */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Max emails:</label>
                <input
                  type="number"
                  value={maxMessages}
                  onChange={e => setMaxMessages(Math.max(0, Number(e.target.value)))}
                  style={{
                    width: 80, padding: '4px 8px', background: 'var(--bg)', border: '1px solid var(--border)',
                    borderRadius: 4, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 12,
                    textAlign: 'right',
                  }}
                />
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>0 = unlimited</span>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => handleSync(true)}
                  disabled={syncing}
                  style={{
                    padding: '6px 16px', borderRadius: 6, border: 'none',
                    background: 'var(--primary)', color: '#fff', fontSize: 12, fontWeight: 600,
                    opacity: syncing ? 0.5 : 1, cursor: syncing ? 'default' : 'pointer',
                  }}
                >
                  {syncing ? 'Syncing...' : 'Full Sync'}
                </button>
                <button
                  onClick={() => handleSync(false)}
                  disabled={syncing}
                  style={{
                    padding: '6px 16px', borderRadius: 6, border: '1px solid var(--border)',
                    background: 'transparent', color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600,
                    opacity: syncing ? 0.5 : 1, cursor: syncing ? 'default' : 'pointer',
                  }}
                >
                  Incremental
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Storage</h3>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'grid', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Total indexed</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{fmtSize(stats?.total_size_bytes ?? 0)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Gmail space freed</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>{fmtSize(stats?.deleted_from_gmail_size ?? 0)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Deleted from Gmail</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{(stats?.deleted_from_gmail ?? 0).toLocaleString()} emails</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
