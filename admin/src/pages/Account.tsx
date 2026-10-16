import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Card, ErrorBox, Page, errMsg } from '../ui';

export function AccountPage() {
  const { admin } = useAuth();
  if (!admin) return null;
  return (
    <Page title="My account">
      <Card className="narrow">
        <div className="row wrap"><strong>{admin.email}</strong><Badge value={admin.role} /></div>
      </Card>
      <ChangePassword />
      <TwoFactor />
    </Page>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (next !== again) {
      setError('The new passwords do not match.');
      return;
    }
    try {
      await api('/me/password', { method: 'POST', body: { current_password: current, new_password: next } });
      setDone(true);
      setCurrent(''); setNext(''); setAgain('');
    } catch (err) {
      setError(errMsg(err));
    }
  };

  return (
    <Card className="narrow">
      <h3>Change password</h3>
      <form className="form" onSubmit={submit}>
        <label>Current password<input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required /></label>
        <label>New password (at least 10 characters)<input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} minLength={10} required /></label>
        <label>New password again<input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required /></label>
        <ErrorBox message={error} />
        {done ? <p className="ok">Password changed.</p> : null}
        <Button type="submit">Change password</Button>
      </form>
    </Card>
  );
}

function TwoFactor() {
  const { admin, refresh } = useAuth();
  const [step, setStep] = useState<'idle' | 'password' | 'scan' | 'disable'>('idle');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setStep('idle'); setPassword(''); setCode(''); setSetup(null); setError(null); };

  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      setSetup(await api('/me/2fa/setup', { method: 'POST', body: { password } }));
      setStep('scan');
      setPassword('');
    } catch (err) {
      setError(errMsg(err));
    }
  };
  const enable = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api('/me/2fa/enable', { method: 'POST', body: { code } });
      await refresh();
      reset();
    } catch (err) {
      setError(errMsg(err));
    }
  };
  const disable = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api('/me/2fa/disable', { method: 'POST', body: { password, code } });
      await refresh();
      reset();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  return (
    <Card className="narrow">
      <h3>Two-factor login</h3>
      <p className="muted small">Adds a 6-digit code from an authenticator app (Google Authenticator, Authy, 1Password…) when you sign in. Recommended for everyone, especially superadmins. If you lose your phone, a superadmin can switch it off for you.</p>
      <p>Status: <Badge value={admin?.totp_enabled ? 'active' : 'disabled'} /></p>

      {step === 'idle' && !admin?.totp_enabled ? <Button onClick={() => setStep('password')}>Set up</Button> : null}
      {step === 'idle' && admin?.totp_enabled ? <Button variant="danger" onClick={() => setStep('disable')}>Turn off</Button> : null}

      {step === 'password' ? (
        <form className="form" onSubmit={start}>
          <label>Confirm your password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus /></label>
          <ErrorBox message={error} />
          <div className="row"><Button type="submit">Continue</Button><Button type="button" variant="ghost" onClick={reset}>Cancel</Button></div>
        </form>
      ) : null}

      {step === 'scan' && setup ? (
        <form className="form" onSubmit={enable}>
          <p>1. Scan this with your authenticator app:</p>
          <div className="qr"><QRCodeSVG value={setup.otpauth_uri} size={168} /></div>
          <p className="small muted">Cannot scan? Enter this key by hand: <code>{setup.secret}</code></p>
          <label>2. Enter the 6-digit code it shows<input inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} required autoComplete="one-time-code" /></label>
          <ErrorBox message={error} />
          <div className="row"><Button type="submit">Turn on</Button><Button type="button" variant="ghost" onClick={reset}>Cancel</Button></div>
        </form>
      ) : null}

      {step === 'disable' ? (
        <form className="form" onSubmit={disable}>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus /></label>
          <label>Current code<input inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} required autoComplete="one-time-code" /></label>
          <ErrorBox message={error} />
          <div className="row"><Button type="submit" variant="danger">Turn off</Button><Button type="button" variant="ghost" onClick={reset}>Cancel</Button></div>
        </form>
      ) : null}
    </Card>
  );
}
