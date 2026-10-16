import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth';
import { Button } from './ui';
import { useEffect, useState } from 'react';
import { api } from './api';
import type { Paged, Report } from './api';
import { AccountPage } from './pages/Account';
import { AdminsPage } from './pages/Admins';
import { PoemsPage } from './pages/Poems';
import { ReportsPage } from './pages/Reports';
import { SystemPage } from './pages/System';
import { AuditPage } from './pages/Audit';
import { ContentPage } from './pages/Content';
import { CreationsPage } from './pages/Creations';
import { DashboardPage } from './pages/Dashboard';
import { LoginPage } from './pages/Login';
import { SettingsPage } from './pages/Settings';
import { TransactionsPage } from './pages/Transactions';
import { UserDetailPage, UsersPage } from './pages/Users';

export function App() {
  const { admin, loading, can, logout } = useAuth();
  const [openReports, setOpenReports] = useState(0);

  // A small badge on the Reports link; refreshed every minute while signed in.
  useEffect(() => {
    if (!admin) return;
    const load = () => api<Paged<Report>>('/reports?status=open&limit=1').then((r) => setOpenReports(r.total)).catch(() => {});
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [admin]);

  if (loading) return <div className="center muted">Loading…</div>;
  if (!admin) return <LoginPage />;

  const links: [string, string, boolean][] = [
    ['/', 'Dashboard', true],
    ['/users', 'Users', true],
    ['/creations', 'Creations', true],
    ['/reports', 'Reports', true],
    ['/poems', 'Poems', true],
    ['/transactions', 'Transactions', true],
    ['/content', 'Content', true],
    ['/settings', 'Settings', true],
    ['/system', 'System', true],
    ['/admins', 'Admins', can('manage_admins')],
    ['/audit', 'Audit log', can('view_audit')],
    ['/account', 'My account', true],
  ];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">Tweezers<span>admin</span></div>
        <nav>
          {links.filter(([, , show]) => show).map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>{label}{to === '/reports' && openReports > 0 ? <span className="count">{openReports}</span> : null}</NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="small">{admin.email}</div>
          <div className="muted small">{admin.role}</div>
          <Button variant="ghost" onClick={logout}>Sign out</Button>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/users/:id" element={<UserDetailPage />} />
          <Route path="/creations" element={<CreationsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/poems" element={<PoemsPage />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/content" element={<ContentPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admins" element={can('manage_admins') ? <AdminsPage /> : <Navigate to="/" />} />
          <Route path="/audit" element={can('view_audit') ? <AuditPage /> : <Navigate to="/" />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
