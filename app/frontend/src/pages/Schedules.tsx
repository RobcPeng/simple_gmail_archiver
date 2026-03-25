import { useEffect, useState } from 'react';
import { api, Schedule, Rule } from '../api';

const cardStyle = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: 20, marginBottom: 24 };
const inputStyle = {
  padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--border)',
  borderRadius: 4, color: 'var(--text-primary)', fontSize: 12, width: '100%',
};
const btnStyle = {
  padding: '6px 16px', borderRadius: 6, border: 'none', fontSize: 12,
  fontWeight: 600 as const, cursor: 'pointer' as const,
};

export default function Schedules() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [newSchedule, setNewSchedule] = useState({ name: '', cron_expression: '0 2 * * 0', filter_label: '' });
  const [newRule, setNewRule] = useState({ name: '', rule_type: 'sender', pattern: '', classification: 'junk', priority: 100 });

  const load = () => {
    api.listSchedules().then(setSchedules).catch(() => {});
    api.listRules().then(setRules).catch(() => {});
  };

  useEffect(load, []);

  const createSchedule = async () => {
    if (!newSchedule.name) return;
    await api.createSchedule({
      name: newSchedule.name,
      cron_expression: newSchedule.cron_expression,
      filter_rules: newSchedule.filter_label ? { label: newSchedule.filter_label } : {},
      require_classification: true,
      enabled: true,
    } as any);
    setNewSchedule({ name: '', cron_expression: '0 2 * * 0', filter_label: '' });
    load();
  };

  const createRule = async () => {
    if (!newRule.name || !newRule.pattern) return;
    await api.createRule(newRule as any);
    setNewRule({ name: '', rule_type: 'sender', pattern: '', classification: 'junk', priority: 100 });
    load();
  };

  return (
    <div>
      <div className="page-header">
        <h2>Schedules & Rules</h2>
        <p>Manage deletion schedules and classification rules</p>
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Deletion Schedules</h3>
        {schedules.map(s => (
          <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <div style={{ fontWeight: 500, fontSize: 13 }}>{s.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                {s.cron_expression} {s.enabled ? '' : '(disabled)'}
              </div>
            </div>
            <button onClick={() => { api.deleteSchedule(s.id); load(); }}
              style={{ ...btnStyle, background: 'rgba(244,63,94,0.1)', color: '#f43f5e' }}>
              Delete
            </button>
          </div>
        ))}
        {schedules.length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: 13, padding: '8px 0' }}>No schedules yet</div>}

        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 8, alignItems: 'end' }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Name</label>
            <input style={inputStyle} value={newSchedule.name} onChange={e => setNewSchedule(p => ({ ...p, name: e.target.value }))} placeholder="Weekly Cleanup" />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Cron</label>
            <input style={inputStyle} value={newSchedule.cron_expression} onChange={e => setNewSchedule(p => ({ ...p, cron_expression: e.target.value }))} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Label Filter</label>
            <input style={inputStyle} value={newSchedule.filter_label} onChange={e => setNewSchedule(p => ({ ...p, filter_label: e.target.value }))} placeholder="CATEGORY_PROMOTIONS" />
          </div>
          <button onClick={createSchedule} style={{ ...btnStyle, background: 'var(--primary)', color: '#fff', height: 30 }}>Add</button>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Classification Rules</h3>
        {rules.map(r => (
          <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <div style={{ fontWeight: 500, fontSize: 13 }}>
                {r.name}
                <span style={{
                  marginLeft: 8, fontSize: 10, padding: '1px 6px', borderRadius: 3,
                  background: r.classification === 'junk' ? 'rgba(244,63,94,0.15)' : 'rgba(16,185,129,0.15)',
                  color: r.classification === 'junk' ? '#f43f5e' : '#10b981',
                  fontFamily: 'var(--font-mono)', textTransform: 'uppercase' as const,
                }}>{r.classification}</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                {r.rule_type}: {r.pattern} (priority: {r.priority})
              </div>
            </div>
            <button onClick={() => { api.deleteRule(r.id); load(); }}
              style={{ ...btnStyle, background: 'rgba(244,63,94,0.1)', color: '#f43f5e' }}>
              Delete
            </button>
          </div>
        ))}
        {rules.length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: 13, padding: '8px 0' }}>No rules yet</div>}

        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr auto 1fr auto auto auto', gap: 8, alignItems: 'end' }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Name</label>
            <input style={inputStyle} value={newRule.name} onChange={e => setNewRule(p => ({ ...p, name: e.target.value }))} placeholder="Block newsletters" />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Type</label>
            <select style={{ ...inputStyle, width: 100 }} value={newRule.rule_type} onChange={e => setNewRule(p => ({ ...p, rule_type: e.target.value }))}>
              <option value="sender">sender</option>
              <option value="domain">domain</option>
              <option value="label">label</option>
              <option value="keyword">keyword</option>
              <option value="size">size</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Pattern</label>
            <input style={inputStyle} value={newRule.pattern} onChange={e => setNewRule(p => ({ ...p, pattern: e.target.value }))} placeholder="spam@example.com" />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Class</label>
            <select style={{ ...inputStyle, width: 80 }} value={newRule.classification} onChange={e => setNewRule(p => ({ ...p, classification: e.target.value }))}>
              <option value="junk">junk</option>
              <option value="keep">keep</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Priority</label>
            <input style={{ ...inputStyle, width: 60 }} type="number" value={newRule.priority} onChange={e => setNewRule(p => ({ ...p, priority: Number(e.target.value) }))} />
          </div>
          <button onClick={createRule} style={{ ...btnStyle, background: 'var(--primary)', color: '#fff', height: 30 }}>Add</button>
        </div>
      </div>
    </div>
  );
}
