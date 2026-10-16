import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { Paged, PoemRow } from '../api';
import { Badge, Button, Card, ErrorBox, Page, Pager, fmtDate, useLoad } from '../ui';

const LIMIT = 20;

export function PoemsPage() {
  const [q, setQ] = useState('');
  const [term, setTerm] = useState('');
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useLoad(() => api<Paged<PoemRow>>(`/poems?q=${encodeURIComponent(term)}&limit=${LIMIT}&offset=${offset}`), [term, offset]);

  return (
    <Page title="Poems">
      <p className="muted small">Search the text of poems for moderation. To act on one, open its video under Creations or the creator under Users.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); setOffset(0); setTerm(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search poem text" aria-label="Search poems" />
        <Button type="submit">Search</Button>
      </form>
      <ErrorBox message={error} />
      <Card>
        <table>
          <thead><tr><th>Poem</th><th>Source</th><th>Status</th><th>By</th><th>Created</th></tr></thead>
          <tbody>
            {data?.items.map((p) => (
              <tr key={p.id}>
                <td className="clip">{p.content ?? '(AI choices not picked yet)'}</td>
                <td>{p.source === 'ai_generated' ? 'AI' : 'Written'}</td>
                <td><Badge value={p.status} /></td>
                <td><Link to={`/users/${p.user_id}`}>{p.user_name || 'open'}</Link></td>
                <td>{fmtDate(p.created_at)}</td>
              </tr>
            ))}
            {data && data.items.length === 0 ? <tr><td colSpan={5} className="muted">No poems found</td></tr> : null}
          </tbody>
        </table>
        {loading && !data ? <p className="muted">Loading…</p> : null}
        {data ? <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} /> : null}
      </Card>
    </Page>
  );
}
