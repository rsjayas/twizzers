import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { Creation, Paged } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Card, ErrorBox, Modal, Page, Pager, errMsg, fmtDate, useLoad } from '../ui';

const LIMIT = 25;
const STATUSES = ['', 'rendering', 'ready', 'failed', 'removed'];

export function CreationsPage() {
  const { can } = useAuth();
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [reasonFor, setReasonFor] = useState<{ creation: Creation; kind: 'takedown' | 'restore' } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, error, loading, reload } = useLoad(() => api<Paged<Creation>>(`/creations?status=${status}&limit=${LIMIT}&offset=${offset}`), [status, offset]);

  const retry = async (c: Creation) => {
    setActionError(null);
    try {
      await api(`/creations/${c.id}/retry`, { method: 'POST' });
      reload();
    } catch (e) {
      setActionError(errMsg(e));
    }
  };

  return (
    <Page
      title="Creations"
      actions={
        <select value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value); }} aria-label="Status">
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      }
    >
      <ErrorBox message={error ?? actionError} />
      <Card>
        <table>
          <thead><tr><th>Status</th><th>Poem</th><th>User</th><th>Views</th><th>Created</th><th>Links</th><th /></tr></thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.id}>
                <td><Badge value={c.status} /></td>
                <td className="clip">{c.poem ?? '-'}</td>
                <td><Link to={`/users/${c.user_id}`}>open</Link></td>
                <td>{c.recipient_view_count}</td>
                <td>{fmtDate(c.created_at)}</td>
                <td className="row">
                  {c.rendered_video_url ? <a href={c.rendered_video_url} target="_blank" rel="noreferrer">video</a> : null}
                  {c.status !== 'removed' ? <a href={`/v/${c.share_link_slug}`} target="_blank" rel="noreferrer">page</a> : null}
                </td>
                <td className="row">
                  {can('retry_render') && (c.status === 'failed' || c.status === 'rendering') ? <Button variant="ghost" onClick={() => retry(c)}>Retry</Button> : null}
                  {can('takedown') && c.status !== 'removed' ? <Button variant="danger" onClick={() => setReasonFor({ creation: c, kind: 'takedown' })}>Take down</Button> : null}
                  {can('takedown') && c.status === 'removed' ? <Button variant="ghost" onClick={() => setReasonFor({ creation: c, kind: 'restore' })}>Restore</Button> : null}
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 ? <tr><td colSpan={7} className="muted">Nothing here</td></tr> : null}
          </tbody>
        </table>
        {loading && !data ? <p className="muted">Loading…</p> : null}
        {data ? <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} /> : null}
      </Card>
      {reasonFor ? <ReasonModal {...reasonFor} onClose={() => setReasonFor(null)} onDone={() => { setReasonFor(null); reload(); }} /> : null}
    </Page>
  );
}

function ReasonModal({ creation, kind, onClose, onDone }: { creation: Creation; kind: 'takedown' | 'restore'; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/creations/${creation.id}/${kind}`, { method: 'POST', body: { reason } });
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={kind === 'takedown' ? 'Take down this video?' : 'Restore this video?'} onClose={onClose}>
      <p className="muted">{kind === 'takedown' ? 'The public link will stop working immediately.' : 'The public link will work again.'}</p>
      <form className="form" onSubmit={submit}>
        <label>Reason (saved in the audit log)<input value={reason} onChange={(e) => setReason(e.target.value)} minLength={3} required autoFocus /></label>
        <ErrorBox message={error} />
        <Button type="submit" variant={kind === 'takedown' ? 'danger' : 'primary'} disabled={busy}>{kind === 'takedown' ? 'Take down' : 'Restore'}</Button>
      </form>
    </Modal>
  );
}
