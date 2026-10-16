import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { Paged, Txn } from '../api';
import { Badge, Card, ErrorBox, Page, Pager, fmtDate, rupees, useLoad } from '../ui';

const LIMIT = 25;
const STATUSES = ['', 'created', 'paid', 'failed', 'adjusted'];

export function TransactionsPage() {
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useLoad(() => api<Paged<Txn>>(`/transactions?status=${status}&limit=${LIMIT}&offset=${offset}`), [status, offset]);

  return (
    <Page
      title="Transactions"
      actions={
        <select value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value); }} aria-label="Status">
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      }
    >
      <p className="muted small">"created" = checkout started but not paid. "adjusted" = credits added or removed by an admin.</p>
      <ErrorBox message={error} />
      <Card>
        <table>
          <thead><tr><th>Status</th><th>Credits</th><th>Amount</th><th>User</th><th>Cashfree order</th><th>Note</th><th>When</th></tr></thead>
          <tbody>
            {data?.items.map((t) => (
              <tr key={t.id}>
                <td><Badge value={t.status} /></td>
                <td>{t.credits > 0 ? `+${t.credits}` : t.credits}</td>
                <td>{rupees(t.amount_inr)}</td>
                <td><Link to={`/users/${t.user_id}`}>open</Link></td>
                <td className="clip">{t.cashfree_order_id ?? '-'}</td>
                <td>{t.note ?? ''}</td>
                <td>{fmtDate(t.paid_at ?? t.created_at)}</td>
              </tr>
            ))}
            {data && data.items.length === 0 ? <tr><td colSpan={7} className="muted">Nothing here</td></tr> : null}
          </tbody>
        </table>
        {loading && !data ? <p className="muted">Loading…</p> : null}
        {data ? <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} /> : null}
      </Card>
    </Page>
  );
}
