import { useState } from 'react';
import { api } from '../api';
import type { Admin } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Card, ErrorBox, Modal, Page, errMsg, fmtDate, useLoad } from '../ui';

const ROLES = ['superadmin', 'support', 'content'];
const ROLE_HELP: Record<string, string> = {
  superadmin: 'Everything, including settings, admins and the audit log.',
  support: 'Users, credit adjustments, retry renders, take down videos.',
  content: 'Templates, music and credit packs.',
};

export function AdminsPage() {
  const { admin: me } = useAuth();
  const { data, error, reload } = useLoad(() => api<Admin[]>('/admins'), []);
  const [creating, setCreating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const patch = async (a: Admin, body: Record<string, unknown>) => {
    setActionError(null);
    try {
      await api(`/admins/${a.id}`, { method: 'PATCH', body });
      reload();
    } catch (e) {
      setActionError(errMsg(e));
    }
  };

  const resetPassword = (a: Admin) => {
    const password = window.prompt(`New password for ${a.email} (min 10 characters):`);
    if (password) patch(a, { password });
  };

  return (
    <Page title="Admins" actions={<Button onClick={() => setCreating(true)}>Add admin</Button>}>
      <ErrorBox message={error ?? actionError} />
      <Card>
        <table>
          <thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Last sign-in</th><th /></tr></thead>
          <tbody>
            {data?.map((a) => (
              <tr key={a.id}>
                <td>{a.email}{a.id === me?.id ? ' (you)' : ''}</td>
                <td>
                  <select value={a.role} disabled={a.id === me?.id} onChange={(e) => patch(a, { role: e.target.value })} aria-label={`Role for ${a.email}`}>
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td><Badge value={a.is_active ? 'active' : 'disabled'} /></td>
                <td>{fmtDate(a.last_login_at)}</td>
                <td className="row">
                  <Button variant="ghost" onClick={() => resetPassword(a)}>Reset password</Button>
                  {a.id !== me?.id ? (
                    <Button variant={a.is_active ? 'danger' : 'ghost'} onClick={() => patch(a, { is_active: !a.is_active })}>{a.is_active ? 'Disable' : 'Enable'}</Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="muted small">{ROLES.map((r) => <li key={r}><strong>{r}</strong>: {ROLE_HELP[r]}</li>)}</ul>
      </Card>
      {creating ? <CreateAdmin onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload(); }} /> : null}
    </Page>
  );
}

function CreateAdmin({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('support');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api('/admins', { method: 'POST', body: { email, password, role } });
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Add admin" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></label>
        <label>Temporary password (min 10 characters)<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={10} required autoComplete="new-password" /></label>
        <label>Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>{ROLES.map((r) => <option key={r} value={r}>{r}</option>)}</select>
        </label>
        <p className="muted small">{ROLE_HELP[role]}</p>
        <ErrorBox message={error} />
        <Button type="submit" disabled={busy}>Create</Button>
      </form>
    </Modal>
  );
}
