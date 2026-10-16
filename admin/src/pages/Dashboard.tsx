import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import type { Stats } from '../api';
import { Link } from 'react-router-dom';
import { Badge, Card, ErrorBox, Page, Stat, rupees, useLoad } from '../ui';

const shortDate = (d: string) => d.slice(5);

export function DashboardPage() {
  const [days, setDays] = useState(30);
  const { data, error, loading } = useLoad(() => api<Stats>(`/stats?days=${days}`), [days]);

  return (
    <Page
      title="Dashboard"
      actions={
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Range">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      }
    >
      <ErrorBox message={error} />
      {loading && !data ? <p className="muted">Loading…</p> : null}
      {data ? (
        <>
          <div className="grid stats">
            <Stat label="Users" value={data.totals.users} />
            <Stat label="Poems" value={data.totals.poems} />
            <Stat label="Videos made" value={data.totals.creations} />
            <Stat label="Shares" value={data.totals.shares} />
            <Stat label="Revenue" value={rupees(data.totals.revenue_inr)} hint="paid credit purchases" />
            <Stat label="Credits held by users" value={data.totals.credits_outstanding} />
            <Stat label="Open reports" value={data.totals.open_reports} hint={data.totals.open_reports ? 'needs review' : 'all clear'} />
            <Stat label="Render failures" value={`${Math.round(data.render_failure_rate * 100)}%`} hint={`of videos in this range`} />
          </div>

          <div className="grid charts">
            <Card>
              <h3>Activity per day</h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={data.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tickFormatter={shortDate} stroke="var(--muted)" fontSize={12} />
                  <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="signups" name="Sign-ups" stroke="#d1416b" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="poems" name="Poems" stroke="#4a6cf7" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="creations" name="Videos" stroke="#16a085" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="shares" name="Shares" stroke="#e08a00" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
            <Card>
              <h3>Revenue per day (₹)</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={data.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tickFormatter={shortDate} stroke="var(--muted)" fontSize={12} />
                  <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} />
                  <Tooltip />
                  <Bar dataKey="revenue_inr" name="Revenue" fill="#d1416b" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <div className="grid charts">
            <Card>
              <h3>How far people get</h3>
              <p className="muted small">Accounts that reached each step (all time).</p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart layout="vertical" data={[
                  { step: 'Signed up', n: data.funnel.signed_up },
                  { step: 'Made a poem', n: data.funnel.made_a_poem },
                  { step: 'Made a video', n: data.funnel.made_a_video },
                  { step: 'Shared it', n: data.funnel.shared },
                ]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" allowDecimals={false} stroke="var(--muted)" fontSize={12} />
                  <YAxis type="category" dataKey="step" width={100} stroke="var(--muted)" fontSize={12} />
                  <Tooltip />
                  <Bar dataKey="n" name="People" fill="#d1416b" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card>
              <h3>Shares by channel</h3>
              {data.shares_by_channel.length ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data.shares_by_channel}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="name" stroke="var(--muted)" fontSize={12} />
                    <YAxis allowDecimals={false} stroke="var(--muted)" fontSize={12} />
                    <Tooltip />
                    <Bar dataKey="count" name="Shares" fill="#e08a00" />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p className="muted">No shares in this range.</p>}
            </Card>
          </div>

          <div className="grid charts">
            <Card>
              <h3>Most used styles</h3>
              <table><tbody>
                {data.top_templates.map((t) => <tr key={t.name}><td>{t.name}</td><td>{t.count}</td></tr>)}
                {data.top_templates.length === 0 ? <tr><td className="muted">No videos in this range</td></tr> : null}
              </tbody></table>
            </Card>
            <Card>
              <h3>Most used music</h3>
              <table><tbody>
                {data.top_music.map((t) => <tr key={t.name}><td>{t.name}</td><td>{t.count}</td></tr>)}
                {data.top_music.length === 0 ? <tr><td className="muted">No videos in this range</td></tr> : null}
              </tbody></table>
            </Card>
          </div>

          {data.totals.open_reports > 0 ? (
            <Card><strong>{data.totals.open_reports} open report{data.totals.open_reports === 1 ? '' : 's'}</strong> waiting. <Link to="/reports">Review them</Link></Card>
          ) : null}

          <Card>
            <h3>Video render status</h3>
            <div className="row wrap">
              {Object.entries(data.creations_by_status).map(([status, n]) => (
                <span key={status} className="row"><Badge value={status} /> <strong>{n}</strong></span>
              ))}
              {Object.keys(data.creations_by_status).length === 0 ? <span className="muted">No videos yet</span> : null}
            </div>
          </Card>
        </>
      ) : null}
    </Page>
  );
}
