import { useState } from 'react';
import { api } from '../api';

export default function Login() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleConnect = async () => {
    setLoading(true);
    setError('');
    try {
      const r = await api.startAuth() as { auth_url: string };
      // Open OAuth in same window — it'll redirect back
      window.location.href = r.auth_url;
    } catch (e) {
      setError('Could not start authentication. Make sure client_secret.json is in the credentials/ directory.');
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <div style={{
        width: 420,
        padding: 48,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        textAlign: 'center',
      }}>
        {/* Logo */}
        <div style={{
          width: 64, height: 64, margin: '0 auto 24px',
          borderRadius: 16,
          background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(99,102,241,0.05))',
          border: '1px solid rgba(99,102,241,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28,
        }}>
          &#9993;
        </div>

        <h1 style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 22,
          fontWeight: 600,
          color: 'var(--text-primary)',
          marginBottom: 6,
          letterSpacing: '-0.3px',
        }}>
          GmailVault
        </h1>

        <p style={{
          fontSize: 13,
          color: 'var(--text-secondary)',
          marginBottom: 36,
          lineHeight: 1.6,
        }}>
          Connect your Gmail account to start archiving,<br />
          searching, and managing your emails locally.
        </p>

        {/* Steps */}
        <div style={{
          textAlign: 'left',
          marginBottom: 32,
          padding: '16px 20px',
          background: 'var(--bg)',
          borderRadius: 8,
          fontSize: 12,
          lineHeight: 2,
          color: 'var(--text-secondary)',
        }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)', fontWeight: 600, flexShrink: 0 }}>1.</span>
            <span>Emails are synced and indexed locally in SQLite</span>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)', fontWeight: 600, flexShrink: 0 }}>2.</span>
            <span>Non-junk emails are archived as .eml files to R2</span>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)', fontWeight: 600, flexShrink: 0 }}>3.</span>
            <span>Review, classify, and schedule bulk deletions</span>
          </div>
        </div>

        <button
          onClick={handleConnect}
          disabled={loading}
          style={{
            width: '100%',
            padding: '12px 24px',
            borderRadius: 8,
            border: 'none',
            background: loading ? 'rgba(99,102,241,0.5)' : 'var(--primary)',
            color: '#fff',
            fontSize: 14,
            fontWeight: 600,
            cursor: loading ? 'default' : 'pointer',
            transition: 'background 0.15s',
            fontFamily: 'var(--font-sans)',
          }}
          onMouseEnter={e => { if (!loading) (e.target as HTMLButtonElement).style.background = 'var(--primary-hover)'; }}
          onMouseLeave={e => { if (!loading) (e.target as HTMLButtonElement).style.background = 'var(--primary)'; }}
        >
          {loading ? 'Redirecting to Google...' : 'Connect Gmail Account'}
        </button>

        {error && (
          <div style={{
            marginTop: 16,
            padding: '10px 14px',
            borderRadius: 6,
            background: 'rgba(244,63,94,0.1)',
            color: 'var(--danger)',
            fontSize: 12,
            textAlign: 'left',
          }}>
            {error}
          </div>
        )}

        <p style={{
          marginTop: 24,
          fontSize: 11,
          color: 'var(--text-secondary)',
          opacity: 0.6,
        }}>
          Your data stays local. Only Gmail API access is used for sync.
        </p>
      </div>
    </div>
  );
}
