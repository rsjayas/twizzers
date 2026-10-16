import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Settings } from '../api';
import { useAuth } from '../auth';
import { Button, Card, ErrorBox, Page, errMsg, useLoad } from '../ui';

export function SettingsPage() {
  const { can } = useAuth();
  const { data, error, reload } = useLoad(() => api<Settings>('/settings'), []);
  const [payments, setPayments] = useState(false);
  const [cost, setCost] = useState('5');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const editable = can('manage_settings');

  useEffect(() => {
    if (data) {
      setPayments(data.payments_enabled);
      setCost(String(data.cost_per_story_credits));
    }
  }, [data]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);
    try {
      await api('/settings', { method: 'PUT', body: { payments_enabled: payments, cost_per_story_credits: Number(cost) } });
      setSaved(true);
      reload();
    } catch (err) {
      setSaveError(errMsg(err));
    }
  };

  return (
    <Page title="Settings">
      <ErrorBox message={error} />
      <Card className="narrow">
        <form className="form" onSubmit={save}>
          <label className="check">
            <input type="checkbox" checked={payments} disabled={!editable} onChange={(e) => setPayments(e.target.checked)} />
            Payments enabled (poems cost credits and checkout is open)
          </label>
          <p className="muted small">Off means everything is free. Turn on only after Cashfree is set up and tested.</p>
          <label>Credits per AI poem
            <input type="number" min={0} max={1000} value={cost} disabled={!editable} onChange={(e) => setCost(e.target.value)} />
          </label>
          <ErrorBox message={saveError} />
          {saved ? <p className="ok">Saved. Changes apply immediately.</p> : null}
          {editable ? <Button type="submit">Save</Button> : <p className="muted small">Only a superadmin can change settings.</p>}
        </form>
      </Card>
    </Page>
  );
}
