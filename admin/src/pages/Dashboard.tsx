import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import type { Stats } from '../api';
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
          </div>

          <div className="grid charts">
            <Card>
              <h3>Sign-ups and poems per day</h3>
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
