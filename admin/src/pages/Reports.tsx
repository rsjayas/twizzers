import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { Paged, Report } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Card, ErrorBox, Modal, Page, Pager, errMsg, fmtDate, useLoad } from '../ui';

const LIMIT = 15;
const REASONS: Record<string, string> = { inappropriate: 'Inappropriate', harassment: 'Harassment or abuse', spam: 'Spam', other: 'Other' };

export function ReportsPage() {
  const { can } = useAuth();
  const [status, setStatus] = useState('open');
  const [offset, setOffset] = useState(0);
  const [acting, setActing] = useState<{ report: Report; action: 'takedown' | 'dismiss' } | null>(null);
  const { data, error, loading, reload } = useLoad(() => api<Paged<Report>>(`/reports?status=${status}&limit=${LIMIT}&offset=${offset}`), [status, offset]);

  return (
    <Page
      title="Reports"
      actions={
        <select value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value); }} aria-label="Status">
          <option value="open">Open</option>
          <option value="actioned">Taken down</option>
          <option value="dismissed">Dismissed</option>
          <option value="">All</option>
        </select>
      }
    >
      <p className="muted small">Viewers can report a video from its public page. Taking one down removes the video and its link, and closes every open report on it.</p>
      <ErrorBox message={error} />
      {data?.items.map((r) => (
        <Card key={r.id}>
          <div className="page-head">
            <div className="row wrap">
              <Badge value={r.status} />
              <strong>{REASONS[r.reason] ?? r.reason}</strong>
              <span className="muted small">{fmtDate(r.created_at)}</span>
            </div>
            <div className="row">
              {r.status === 'open' && can('takedown') ? (
                <>
                  <Button variant="danger" onClick={() => setActing({ report: r, action: 'takedown' })}>Take down</Button>
                  <Button variant="ghost" onClick={() => setActing({ report: r, action: 'dismiss' })}>Dismiss</Button>
                </>
              ) : null}
            </div>
          </div>
          {r.details ? <p>"{r.details}"</p> : null}
          {r.creation ? (
            <>
              <pre className="poem">{r.creation.poem ?? '(no poem text)'}</pre>
              <div className="row small">
                <Badge value={r.creation.status} />
                {r.creation.status !== 'removed' ? <a href={`/v/${r.creation.share_link_slug}`} target="_blank" rel="noreferrer">public page</a> : null}
                {r.creation.rendered_video_url ? <a href={r.creation.rendered_video_url} target="_blank" rel="noreferrer">video</a> : null}
                <Link to={`/users/${r.creation.user_id}`}>creator</Link>
              </div>
            </>
          ) : null}
          {r.handled_by ? <p className="muted small">Handled by {r.handled_by} on {fmtDate(r.handled_at)}{r.resolution_note ? `: ${r.resolution_note}` : ''}</p> : null}
        </Card>
      ))}
      {data && data.items.length === 0 ? <Card><span className="muted">Nothing here.</span></Card> : null}
      {loading && !data ? <p className="muted">Loading…</p> : null}
      {data ? <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} /> : null}
      {acting ? <ResolveModal {...acting} onClose={() => setActing(null)} onDone={() => { setActing(null); reload(); }} /> : null}
    </Page>
  );
}

function ResolveModal({ report, action, onClose, onDone }: { report: Report; action: 'takedown' | 'dismiss'; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/reports/${report.id}/resolve`, { method: 'POST', body: { action, note } });
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };
  return (
    <Modal title={action === 'takedown' ? 'Take down this video?' : 'Dismiss this report?'} onClose={onClose}>
      <p className="muted">{action === 'takedown' ? 'The public link stops working immediately.' : 'The video stays online.'}</p>
      <form className="form" onSubmit={submit}>
        <label>Note (saved in the audit log, optional)<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} autoFocus /></label>
        <ErrorBox message={error} />
        <Button type="submit" variant={action === 'takedown' ? 'danger' : 'primary'} disabled={busy}>{action === 'takedown' ? 'Take down' : 'Dismiss'}</Button>
      </form>
    </Modal>
  );
}
