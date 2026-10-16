import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth';
import { Button } from './ui';
import { AdminsPage } from './pages/Admins';
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
  if (loading) return <div className="center muted">Loading…</div>;
  if (!admin) return <LoginPage />;

  const links: [string, string, boolean][] = [
    ['/', 'Dashboard', true],
    ['/users', 'Users', true],
    ['/creations', 'Creations', true],
    ['/transactions', 'Transactions', true],
    ['/content', 'Content', true],
    ['/settings', 'Settings', true],
    ['/admins', 'Admins', can('manage_admins')],
    ['/audit', 'Audit log', can('view_audit')],
  ];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">Tweezers<span>admin</span></div>
        <nav>
          {links.filter(([, , show]) => show).map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>{label}</NavLink>
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
