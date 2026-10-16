import { useState } from 'react';
import { api } from '../api';
import type { AuditRow, Paged } from '../api';
import { Card, ErrorBox, Page, Pager, fmtDate, useLoad } from '../ui';

const LIMIT = 50;

export function AuditPage() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useLoad(() => api<Paged<AuditRow>>(`/audit?limit=${LIMIT}&offset=${offset}`), [offset]);

  return (
    <Page title="Audit log">
      <p className="muted small">Every change made through this dashboard. Entries cannot be edited here.</p>
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
