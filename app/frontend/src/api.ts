const BASE = '/api';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

export interface Email {
  id: string;
  subject: string;
  sender: string;
  sender_email: string;
  snippet: string;
  date: string;
  classification: string | null;
  has_attachments: boolean;
  size_bytes: number;
  eml_path: string | null;
}

export interface EmailSearchResult {
  emails: Email[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  total_emails: number;
  total_size_bytes: number;
  classified_archive: number;
  classified_archive_size: number;
  classified_keep: number;
  classified_keep_size: number;
  classified_junk: number;
  classified_junk_size: number;
  unclassified: number;
  unclassified_size: number;
  deleted_from_gmail: number;
  deleted_from_gmail_size: number;
}

export interface SyncStatus {
  is_syncing: boolean;
  account_email: string | null;
  last_history_id: string | null;
  last_full_sync: string | null;
  synced_messages: number;
}

export interface AuthStatus {
  authenticated: boolean;
  has_client_secret?: boolean;
  email?: string;
}

export interface Schedule {
  id: number;
  name: string;
  cron_expression: string;
  filter_rules: Record<string, string>;
  require_classification: boolean;
  enabled: boolean;
  last_run: string | null;
  created_at: string;
}

export interface Rule {
  id: number;
  name: string;
  rule_type: string;
  pattern: string;
  classification: string;
  priority: number;
  enabled: boolean;
  created_at: string;
}

export const api = {
  searchEmails: (p: Record<string, string>) =>
    request<EmailSearchResult>(`/emails?${new URLSearchParams(p)}`),
  getEmail: (id: string) => request<Email>(`/emails/${id}`),
  classifyEmail: (id: string, c: string) =>
    request(`/emails/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ classification: c }),
    }),
  bulkClassify: (ids: string[], c: string) =>
    request('/emails/classify-bulk', {
      method: 'POST',
      body: JSON.stringify({ email_ids: ids, classification: c }),
    }),
  getStats: () => request<Stats>('/stats'),
  getSyncStatus: () => request<SyncStatus>('/sync/status'),
  triggerSync: (full = false) =>
    request(`/sync?full=${full}`, { method: 'POST' }),
  getAuthStatus: () => request<AuthStatus>('/auth/status'),
  startAuth: () => request('/auth/start', { method: 'POST' }),
  listSchedules: () => request<Schedule[]>('/schedules'),
  createSchedule: (d: Partial<Schedule>) =>
    request('/schedules', { method: 'POST', body: JSON.stringify(d) }),
  deleteSchedule: (id: number) =>
    request(`/schedules/${id}`, { method: 'DELETE' }),
  listRules: () => request<Rule[]>('/rules'),
  createRule: (d: Partial<Rule>) =>
    request('/rules', { method: 'POST', body: JSON.stringify(d) }),
  deleteRule: (id: number) => request(`/rules/${id}`, { method: 'DELETE' }),
};
