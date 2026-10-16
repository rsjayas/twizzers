import { useState } from 'react';
import { api } from '../api';
import type { AuditRow, Paged } from '../api';
import { Button, Card, ErrorBox, Page, Pager, fmtDate, useLoad } from '../ui';

const LIMIT = 50;

export function AuditPage() {
  const [offset, setOffset] = useState(0);
  const [who, setWho] = useState('');
  const [what, setWhat] = useState('');
  const [filter, setFilter] = useState({ who: '', what: '' });
  const { data, error, loading } = useLoad(
    () => api<Paged<AuditRow>>(`/audit?limit=${LIMIT}&offset=${offset}&admin_email=${encodeURIComponent(filter.who)}&action=${encodeURIComponent(filter.what)}`),
    [offset, filter],
  );

  return (
    <Page title="Audit log">
      <p className="muted small">Every change made through this dashboard. Entries cannot be edited here.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); setOffset(0); setFilter({ who, what }); }}>
        <input value={who} onChange={(e) => setWho(e.target.value)} placeholder="Admin email" aria-label="Admin email" />
        <input value={what} onChange={(e) => setWhat(e.target.value)} placeholder="Action starts with… (e.g. user.)" aria-label="Action" />
        <Button type="submit">Filter</Button>
      </form>
      <ErrorBox message={error} />
      <Card>
        <table>
          <thead><tr><th>When</th><th>Admin</th><th>Action</th><th>Target</th><th>Details</th></tr></thead>
          <tbody>
            {data?.items.map((r) => (
              <tr key={r.id}>
                <td>{fmtDate(r.created_at)}</td>
                <td>{r.admin_email ?? '-'}</td>
                <td><code>{r.action}</code></td>
                <td className="clip">{r.target_type ? `${r.target_type} ${r.target_id ?? ''}` : '-'}</td>
                <td className="clip"><code>{r.details ? JSON.stringify(r.details) : ''}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && !data ? <p className="muted">Loading…</p> : null}
        {data ? <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} /> : null}
      </Card>
    </Page>
  );
}
