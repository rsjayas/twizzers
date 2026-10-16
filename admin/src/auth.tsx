import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api, setUnauthorizedHandler, tokenStore } from './api';
import type { Admin } from './api';

type AuthState = {
  admin: Admin | null;
  loading: boolean;
  can: (permission: string) => boolean;
  login: (email: string, password: string, code?: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    setAdmin(null);
  }, []);

  const refresh = useCallback(async () => {
    setAdmin(await api<Admin>('/me'));
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!tokenStore.get()) return;
    api<Admin>('/me').then(setAdmin).catch(logout).finally(() => setLoading(false));
  }, [logout]);

  const login = async (email: string, password: string, code?: string) => {
    const res = await api<{ token: string; admin: Admin }>('/login', { method: 'POST', body: { email, password, code: code || undefined } });
    tokenStore.set(res.token);
    setAdmin(res.admin);
  };

  const can = (permission: string) => Boolean(admin?.permissions.includes(permission));

  return <Ctx.Provider value={{ admin, loading, can, login, logout, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside AuthProvider');
  return v;
}
