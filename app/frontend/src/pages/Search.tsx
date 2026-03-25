import { useState, useCallback } from 'react';
import EmailRow from '../components/EmailRow';
import { api, Email, EmailSearchResult } from '../api';

export default function Search() {
  const [query, setQuery] = useState('');
  const [classification, setClassification] = useState('');
  const [results, setResults] = useState<EmailSearchResult | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const doSearch = useCallback(async (p = 1) => {
    setLoading(true);
    const params: Record<string, string> = { page: String(p), page_size: '50' };
    if (query) params.query = query;
    if (classification) params.classification = classification;
    try {
      const r = await api.searchEmails(params) as EmailSearchResult;
      setResults(r);
      setPage(p);
      setSelected(new Set());
    } catch {}
    setLoading(false);
  }, [query, classification]);

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const bulkClassify = async (c: string) => {
    if (selected.size === 0) return;
    await api.bulkClassify([...selected], c);
    setSelected(new Set());
    doSearch(page);
  };

  const totalPages = results ? Math.ceil(results.total / results.page_size) : 0;

  return (
    <div>
      <div className="page-header">
        <h2>Search</h2>
        <p>Search and manage your archived emails</p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch(1)}
          placeholder="Search emails..."
          style={{
            flex: 1, padding: '8px 14px', background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 6, color: 'var(--text-primary)', fontSize: 13, outline: 'none',
          }}
        />
        <select
          value={classification}
          onChange={e => setClassification(e.target.value)}
          style={{
            padding: '8px 12px', background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 6, color: 'var(--text-primary)', fontSize: 13,
          }}
        >
          <option value="">All</option>
          <option value="archive">Archive</option>
          <option value="keep">Keep</option>
          <option value="junk">Junk</option>
          <option value="unclassified">Unclassified</option>
        </select>
        <button
          onClick={() => doSearch(1)}
          style={{
            padding: '8px 20px', background: 'var(--primary)', color: '#fff', border: 'none',
            borderRadius: 6, fontSize: 13, fontWeight: 600,
          }}
        >
          Search
        </button>
      </div>

      {selected.size > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
          padding: '8px 12px', background: 'rgba(99,102,241,0.08)', borderRadius: 6, fontSize: 12,
        }}>
          <span style={{ fontFamily: 'var(--font-mono)' }}>{selected.size}</span> selected
          <button
            onClick={() => bulkClassify('archive')}
            style={{ marginLeft: 8, padding: '3px 10px', borderRadius: 4, border: 'none', background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
          >
            Archive
          </button>
          <button
            onClick={() => bulkClassify('keep')}
            style={{ padding: '3px 10px', borderRadius: 4, border: 'none', background: 'rgba(16,185,129,0.15)', color: '#10b981', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
          >
            Mark Keep
          </button>
          <button
            onClick={() => bulkClassify('junk')}
            style={{ padding: '3px 10px', borderRadius: 4, border: 'none', background: 'rgba(244,63,94,0.15)', color: '#f43f5e', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
          >
            Mark Junk
          </button>
        </div>
      )}

      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        {loading && <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>}
        {results && !loading && results.emails.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>No results found</div>
        )}
        {results && !loading && results.emails.map((email: Email) => (
          <EmailRow key={email.id} email={email} selected={selected.has(email.id)} onToggle={toggleSelect} />
        ))}
      </div>

      {results && totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
          <span>{results.total.toLocaleString()} results</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              disabled={page <= 1}
              onClick={() => doSearch(page - 1)}
              style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: page <= 1 ? 'default' : 'pointer', opacity: page <= 1 ? 0.4 : 1 }}
            >
              Prev
            </button>
            <span style={{ fontFamily: 'var(--font-mono)', padding: '4px 8px' }}>
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => doSearch(page + 1)}
              style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: page >= totalPages ? 'default' : 'pointer', opacity: page >= totalPages ? 0.4 : 1 }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
