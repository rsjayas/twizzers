import React, { useState } from 'react';
import { Text } from 'react-native';
import { auth } from '../auth';
import { AUTH_MODE } from '../config';
import type { User } from '../types';
import { Button, ErrorText, Field, Screen, colors } from '../ui';

export function LoginScreen({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  const sendCode = () =>
    run(async () => {
      await auth.sendCode(phone.trim());
      setCodeSent(true);
    });

  const verify = () =>
    run(async () => {
      onSignedIn(await auth.verify({ name: name.trim(), phone: phone.trim(), code }));
    });

  const needsCode = auth.requiresOtp && codeSent;

  return (
    <Screen title="Tweezers" subtitle="Two bodies, one soul. Turn your feelings into a poem they'll keep.">
      {!needsCode ? (
        <>
          <Field label="Your name" value={name} onChangeText={setName} placeholder="Asha" />
          <Field label="Phone number" value={phone} onChangeText={setPhone} placeholder="+91 98765 43210" keyboardType="phone-pad" />
          <ErrorText message={error} />
          <Button
            label={auth.requiresOtp ? 'Send code' : 'Continue'}
            onPress={auth.requiresOtp ? sendCode : verify}
            loading={busy}
            disabled={phone.trim().length < 8}
          />
        </>
      ) : (
        <>
          <Text style={{ color: colors.muted, marginBottom: 12 }}>We sent a 6-digit code to {phone.trim()}.</Text>
          <Field label="Code" value={code} onChangeText={setCode} placeholder="123456" keyboardType="number-pad" maxLength={6} />
          <ErrorText message={error} />
          <Button label="Verify" onPress={verify} loading={busy} disabled={code.trim().length < 6} />
          <Button label="Use a different number" onPress={() => { setCodeSent(false); setCode(''); setError(null); }} secondary />
        </>
      )}
      {AUTH_MODE === 'dev' ? (
        <Text style={{ color: colors.muted, marginTop: 16, fontSize: 12 }}>
          Dev login: no code is sent. Set EXPO_PUBLIC_AUTH_MODE=firebase for real phone verification.
        </Text>
      ) : null}
    </Screen>
  );
}
