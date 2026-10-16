import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';

export const fmtDate = (iso: string | null) => (iso ? new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString() : '-');
export const rupees = (n: number) => `₹${n.toLocaleString('en-IN')}`;

export function Page({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="page-head"><h1>{title}</h1><div className="row">{actions}</div></div>
      {children}
    </section>
  );
}

export const Card = ({ children, className = '' }: { children: ReactNode; className?: string }) => (
  <div className={`card ${className}`}>{children}</div>
);

export function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="card stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint ? <div className="muted small">{hint}</div> : null}
    </div>
  );
}

export function Badge({ value }: { value: string }) {
  return <span className={`badge badge-${value}`}>{value}</span>;
}

export function ErrorBox({ message }: { message: string | null }) {
  return message ? <div className="error" role="alert">{message}</div> : null;
}

export function Button({ children, variant = 'primary', ...rest }: { variant?: 'primary' | 'ghost' | 'danger' } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...rest} className={`btn btn-${variant} ${rest.className ?? ''}`}>{children}</button>;
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
        <div className="page-head"><h2>{title}</h2><Button variant="ghost" onClick={onClose}>Close</Button></div>
        {children}
      </div>
    </div>
  );
}

export function Pager({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="row pager">
      <span className="muted small">{total} total</span>
      <Button variant="ghost" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button>
      <span className="small">Page {page} of {pages}</span>
      <Button variant="ghost" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</Button>
    </div>
  );
}

/** Runs an async loader and re-runs it when `deps` change or `reload()` is called. */
export function useLoad<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setLoading(true);
    loader()
      .then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : 'Failed to load'); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong');
