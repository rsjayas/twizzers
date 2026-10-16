import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import type { Paged, User, UserDetail } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Card, ErrorBox, Modal, Page, Pager, errMsg, fmtDate, rupees, useLoad } from '../ui';

const LIMIT = 25;

export function UsersPage() {
  const [q, setQ] = useState('');
  const [term, setTerm] = useState('');
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useLoad(() => api<Paged<User>>(`/users?q=${encodeURIComponent(term)}&limit=${LIMIT}&offset=${offset}`), [term, offset]);

  return (
    <Page title="Users">
      <form className="row" onSubmit={(e) => { e.preventDefault(); setOffset(0); setTerm(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, phone, email or user ID" aria-label="Search" />
        <Button type="submit">Search</Button>
      </form>
      <ErrorBox message={error} />
      <Card>
        <table>
          <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Credits</th><th>Joined</th></tr></thead>
          <tbody>
            {data?.items.map((u) => (
              <tr key={u.id}>
                <td><Link to={`/users/${u.id}`}>{u.name || '(no name)'}</Link></td>
                <td>{u.phone ?? '-'}</td><td>{u.email ?? '-'}</td><td>{u.credits_balance}</td><td>{fmtDate(u.created_at)}</td>
              </tr>
            ))}
            {data && data.items.length === 0 ? <tr><td colSpan={5} className="muted">No users found</td></tr> : null}
          </tbody>
        </table>
        {loading && !data ? <p className="muted">Loading…</p> : null}
        {data ? <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} /> : null}
      </Card>
    </Page>
  );
}

export function UserDetailPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const { data: user, error, reload } = useLoad(() => api<UserDetail>(`/users/${id}`), [id]);
  const [adjusting, setAdjusting] = useState(false);

  if (error) return <Page title="User"><ErrorBox message={error} /></Page>;
  if (!user) return <Page title="User"><p className="muted">Loading…</p></Page>;

  return (
    <Page title={user.name || '(no name)'} actions={can('adjust_credits') ? <Button onClick={() => setAdjusting(true)}>Adjust credits</Button> : null}>
      <Link to="/users" className="small">← All users</Link>
      <div className="grid stats">
        <Card><div className="muted small">Phone</div>{user.phone ?? '-'}</Card>
        <Card><div className="muted small">Email</div>{user.email ?? '-'}</Card>
        <Card><div className="muted small">Credits</div><strong>{user.credits_balance}</strong></Card>
        <Card><div className="muted small">Poems</div>{user.poem_count}</Card>
        <Card><div className="muted small">Joined</div>{fmtDate(user.created_at)}</Card>
      </div>
      <Card>
        <h3>Recent videos</h3>
        <table>
          <thead><tr><th>Status</th><th>Poem</th><th>Views</th><th>Created</th></tr></thead>
          <tbody>
            {user.creations.map((c) => (
              <tr key={c.id}><td><Badge value={c.status} /></td><td className="clip">{c.poem ?? '-'}</td><td>{c.recipient_view_count}</td><td>{fmtDate(c.created_at)}</td></tr>
            ))}
            {user.creations.length === 0 ? <tr><td colSpan={4} className="muted">None</td></tr> : null}
          </tbody>
        </table>
      </Card>
      <Card>
        <h3>Credit history</h3>
        <table>
          <thead><tr><th>Status</th><th>Credits</th><th>Paid</th><th>Note</th><th>When</th></tr></thead>
          <tbody>
            {user.transactions.map((t) => (
              <tr key={t.id}><td><Badge value={t.status} /></td><td>{t.credits > 0 ? `+${t.credits}` : t.credits}</td><td>{rupees(t.amount_inr)}</td><td>{t.note ?? ''}</td><td>{fmtDate(t.created_at)}</td></tr>
            ))}
            {user.transactions.length === 0 ? <tr><td colSpan={5} className="muted">None</td></tr> : null}
          </tbody>
        </table>
      </Card>
      {adjusting ? <AdjustCredits userId={user.id} onClose={() => setAdjusting(false)} onDone={() => { setAdjusting(false); reload(); }} /> : null}
    </Page>
  );
}

function AdjustCredits({ userId, onClose, onDone }: { userId: string; onClose: () => void; onDone: () => void }) {
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/users/${userId}/credits`, { method: 'POST', body: { delta: Number(delta), reason } });
      onDone();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Adjust credits" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Change (use a minus sign to remove)<input type="number" value={delta} onChange={(e) => setDelta(e.target.value)} required autoFocus /></label>
        <label>Reason (saved in the audit log)<input value={reason} onChange={(e) => setReason(e.target.value)} minLength={3} required /></label>
        <ErrorBox message={error} />
        <Button type="submit" disabled={busy || !delta || Number(delta) === 0}>Apply</Button>
      </form>
    </Modal>
  );
}
