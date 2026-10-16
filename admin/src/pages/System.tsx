import { api } from '../api';
import type { SystemStatus } from '../api';
import { Badge, Button, Card, ErrorBox, Page, Stat, useLoad } from '../ui';

const yesNo = (ok: boolean | null) => (ok === null ? 'unknown' : ok ? 'ok' : 'down');

export function SystemPage() {
  const { data, error, loading, reload } = useLoad(() => api<SystemStatus>('/system'), []);

  return (
    <Page title="System" actions={<Button variant="ghost" onClick={reload}>Refresh</Button>}>
      <ErrorBox message={error} />
      {loading && !data ? <p className="muted">Checking…</p> : null}
      {data ? (
        <>
          {data.warnings.length ? (
            <Card>
              <h3>Needs attention</h3>
              <ul>{data.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            </Card>
          ) : (
            <Card><span className="ok">Nothing needs attention.</span></Card>
          )}

          <div className="grid stats">
            <Stat label="Open reports" value={data.attention.open_reports} />
            <Stat label="Failed renders (24h)" value={data.attention.failed_renders_24h} />
            <Stat label="Stuck renders (over 15 min)" value={data.attention.stuck_renders} />
          </div>

          <Card>
            <h3>Services</h3>
            <table>
              <tbody>
                <tr><td>Database</td><td><Badge value={yesNo(data.database_ok)} /></td></tr>
                <tr>
                  <td>Render service</td>
                  <td>
                    {data.render_service.configured ? <Badge value={yesNo(data.render_service.reachable)} /> : <Badge value="not set" />}
                    {data.render_service.reachable ? <span className="muted small"> &nbsp;{data.render_service.queued} waiting, {data.render_service.running ? 'rendering now' : 'idle'}</span> : null}
                  </td>
                </tr>
                <tr><td>Claude API (poems)</td><td><Badge value={data.integrations.claude_api ? 'ok' : 'not set'} /></td></tr>
                <tr><td>Firebase sign-in</td><td><Badge value={data.integrations.firebase_auth ? 'ok' : 'not set'} /></td></tr>
                <tr><td>Cashfree payments</td><td><Badge value={data.integrations.cashfree ? 'ok' : 'not set'} /> <span className="muted small">&nbsp;{data.integrations.cashfree_environment}</span></td></tr>
              </tbody>
            </table>
          </Card>

          <Card>
            <h3>Safety switches</h3>
            <table>
              <tbody>
                <tr><td>Dev login bypass (must be off in production)</td><td><Badge value={data.environment.auth_dev_bypass ? 'ON' : 'off'} /></td></tr>
                <tr><td>CDN origin check</td><td><Badge value={data.environment.origin_verify ? 'on' : 'off'} /></td></tr>
                <tr><td>Allowed browser origins</td><td>{data.environment.cors_origins.length ? data.environment.cors_origins.join(', ') : 'none'}</td></tr>
                <tr><td>Payments</td><td><Badge value={data.settings.payments_enabled ? 'on' : 'off'} /></td></tr>
                <tr><td>New sign-ups</td><td><Badge value={data.settings.signups_enabled ? 'on' : 'closed'} /></td></tr>
              </tbody>
            </table>
            <p className="muted small">Secrets are never shown here. Change switches under Settings.</p>
          </Card>
        </>
      ) : null}
    </Page>
  );
}
