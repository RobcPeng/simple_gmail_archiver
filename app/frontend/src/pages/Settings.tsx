import { useEffect, useState } from 'react';
import { api, AuthStatus } from '../api';

const cardStyle = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 20, marginBottom: 16 };

export default function Settings() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);

  useEffect(() => {
    api.getAuthStatus().then(setAuth).catch(() => {});
  }, []);

  const startAuth = async () => {
    try {
      const r = await api.startAuth() as { auth_url: string };
      window.open(r.auth_url, '_blank');
    } catch {}
  };

  return (
    <div>
      <div className="page-header">
        <h2>Settings</h2>
        <p>Manage connections and configuration</p>
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Gmail Connection</h3>
        {auth && (
          <div style={{ fontSize: 13 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: auth.authenticated ? 'var(--success)' : 'var(--danger)',
              }} />
              <span>{auth.authenticated ? 'Connected' : 'Not connected'}</span>
            </div>
            {auth.authenticated && auth.email && (
              <div style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>
                Account: <span style={{ fontFamily: 'var(--font-mono)' }}>{auth.email}</span>
              </div>
            )}
            {!auth.authenticated && (
              <div>
                {auth.has_client_secret ? (
                  <button onClick={startAuth} style={{
                    padding: '6px 16px', borderRadius: 6, border: 'none',
                    background: 'var(--primary)', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  }}>
                    Connect Gmail
                  </button>
                ) : (
                  <div style={{ color: 'var(--warning)', fontSize: 12 }}>
                    Place your Google OAuth <code style={{ fontFamily: 'var(--font-mono)' }}>client_secret.json</code> in the credentials/ directory first.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>R2 Storage</h3>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Configure R2 credentials via environment variables:
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, marginTop: 8, padding: 12, background: 'var(--bg)', borderRadius: 4, lineHeight: 1.8 }}>
            R2_ACCOUNT_ID<br />
            R2_ACCESS_KEY_ID<br />
            R2_SECRET_ACCESS_KEY<br />
            R2_BUCKET_NAME
          </div>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>About</h3>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          <div>GmailVault v0.1.0</div>
          <div style={{ marginTop: 4 }}>Local-first Gmail management and archival system</div>
        </div>
      </div>
    </div>
  );
}
