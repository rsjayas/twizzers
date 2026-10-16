import { useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import { Button, Card, ErrorBox, Modal, Page, errMsg, useLoad } from '../ui';

type Field = { key: string; label: string; kind: 'text' | 'number' | 'tags' | 'bool'; required?: boolean };
type Row = { id: string } & Record<string, unknown>;

const RESOURCES = {
  templates: {
    label: 'Templates',
    fields: [
      { key: 'name', label: 'Name', kind: 'text', required: true },
      { key: 'category', label: 'Category', kind: 'text', required: true },
      { key: 'mood_tags', label: 'Mood tags (comma separated)', kind: 'tags' },
      { key: 'lottie_file_url', label: 'Lottie file URL', kind: 'text' },
      { key: 'rive_file_url', label: 'Rive file URL', kind: 'text' },
      { key: 'preview_thumbnail_url', label: 'Preview image URL', kind: 'text' },
      { key: 'is_active', label: 'Visible in the app', kind: 'bool' },
    ] as Field[],
    columns: ['name', 'category', 'mood_tags', 'is_active'],
    defaults: { is_active: true, mood_tags: [] },
  },
  music: {
    label: 'Music',
    fields: [
      { key: 'title', label: 'Title', kind: 'text', required: true },
      { key: 'artist', label: 'Artist', kind: 'text' },
      { key: 'license_source', label: 'License source', kind: 'text' },
      { key: 'mood_tags', label: 'Mood tags (comma separated)', kind: 'tags' },
      { key: 'audio_file_url', label: 'Audio file URL', kind: 'text', required: true },
      { key: 'duration_seconds', label: 'Duration (seconds)', kind: 'number' },
    ] as Field[],
    columns: ['title', 'artist', 'license_source', 'mood_tags', 'duration_seconds'],
    defaults: { mood_tags: [] },
  },
  packs: {
    label: 'Credit packs',
    fields: [
      { key: 'label', label: 'Label', kind: 'text', required: true },
      { key: 'credits', label: 'Credits', kind: 'number', required: true },
      { key: 'price_inr', label: 'Price (₹)', kind: 'number', required: true },
      { key: 'is_active', label: 'Available to buy', kind: 'bool' },
    ] as Field[],
    columns: ['label', 'credits', 'price_inr', 'is_active'],
    defaults: { is_active: true },
  },
} as const;

type ResourceName = keyof typeof RESOURCES;

const show = (v: unknown) => (Array.isArray(v) ? v.join(', ') : typeof v === 'boolean' ? (v ? 'yes' : 'no') : v == null ? '-' : String(v));

export function ContentPage() {
  const [tab, setTab] = useState<ResourceName>('templates');
  return (
    <Page title="Content">
      <div className="row tabs">
        {(Object.keys(RESOURCES) as ResourceName[]).map((name) => (
          <Button key={name} variant={tab === name ? 'primary' : 'ghost'} onClick={() => setTab(name)}>{RESOURCES[name].label}</Button>
        ))}
      </div>
      <ResourcePanel key={tab} name={tab} />
    </Page>
  );
}

function ResourcePanel({ name }: { name: ResourceName }) {
  const { can } = useAuth();
  const res = RESOURCES[name];
  const { data, error, loading, reload } = useLoad(() => api<Row[]>(`/${name}`), [name]);
  const [editing, setEditing] = useState<Row | 'new' | null>(null);
  const canEdit = can('manage_content');

  return (
    <Card>
      <div className="page-head">
        <span className="muted small">{canEdit ? '' : 'Read only for your role. '}Templates and packs are hidden rather than deleted, because videos and purchases refer to them.</span>
        {canEdit ? <Button onClick={() => setEditing('new')}>Add</Button> : null}
      </div>
      <ErrorBox message={error} />
      <table>
        <thead><tr>{res.columns.map((c) => <th key={c}>{c.replace(/_/g, ' ')}</th>)}<th /></tr></thead>
        <tbody>
          {data?.map((row) => (
            <tr key={row.id}>
              {res.columns.map((c) => <td key={c} className={c === 'name' || c === 'title' ? '' : 'clip'}>{show(row[c])}</td>)}
              <td>{canEdit ? <Button variant="ghost" onClick={() => setEditing(row)}>Edit</Button> : null}</td>
            </tr>
          ))}
          {data && data.length === 0 ? <tr><td colSpan={res.columns.length + 1} className="muted">Nothing yet</td></tr> : null}
        </tbody>
      </table>
      {loading && !data ? <p className="muted">Loading…</p> : null}
      {editing ? (
        <EditModal name={name} row={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); reload(); }} />
      ) : null}
    </Card>
  );
}

function EditModal({ name, row, onClose, onDone }: { name: ResourceName; row: Row | null; onClose: () => void; onDone: () => void }) {
  const res = RESOURCES[name];
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...res.defaults, ...(row ?? {}) }));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (key: string, value: unknown) => setValues((v) => ({ ...v, [key]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = {};
    for (const f of res.fields) {
      const v = values[f.key];
      if (f.kind === 'number') body[f.key] = v === '' || v == null ? null : Number(v);
      else if (f.kind === 'text') body[f.key] = v === '' ? null : v;
      else body[f.key] = v;
    }
    try {
      if (row) await api(`/${name}/${row.id}`, { method: 'PATCH', body });
      else await api(`/${name}`, { method: 'POST', body });
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={row ? `Edit ${res.label.toLowerCase()}` : `Add to ${res.label.toLowerCase()}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        {res.fields.map((f) =>
          f.kind === 'bool' ? (
            <label key={f.key} className="check"><input type="checkbox" checked={Boolean(values[f.key])} onChange={(e) => set(f.key, e.target.checked)} /> {f.label}</label>
          ) : f.kind === 'tags' ? (
            <label key={f.key}>{f.label}
              <input defaultValue={(values[f.key] as string[] | undefined)?.join(', ') ?? ''}
                     onChange={(e) => set(f.key, e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />
            </label>
          ) : (
            <label key={f.key}>{f.label}
              <input type={f.kind === 'number' ? 'number' : 'text'} required={f.required}
                     value={(values[f.key] as string | number | null | undefined) ?? ''} onChange={(e) => set(f.key, e.target.value)} />
            </label>
          ),
        )}
        <ErrorBox message={error} />
        <Button type="submit" disabled={busy}>Save</Button>
      </form>
    </Modal>
  );
}
