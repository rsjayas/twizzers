import React, { useState } from 'react';
import { Text } from 'react-native';
import { auth } from '../auth';
import { AUTH_MODE } from '../config';
import type { User } from '../types';
import { Button, ErrorText, Field, Screen, colors } from '../ui';

export function LoginScreen({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await auth.signIn({ name: name.trim(), phone: phone.trim() }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen title="Tweezers" subtitle="Two bodies, one soul. Turn your feelings into a poem they'll keep.">
      <Field label="Your name" value={name} onChangeText={setName} placeholder="Asha" />
      <Field label="Phone number" value={phone} onChangeText={setPhone} placeholder="+91 98765 43210" keyboardType="phone-pad" />
      <ErrorText message={error} />
      <Button label="Continue" onPress={submit} loading={busy} disabled={phone.trim().length < 8} />
      {AUTH_MODE === 'dev' ? (
        <Text style={{ color: colors.muted, marginTop: 16, fontSize: 12 }}>
          Dev login: no OTP is sent. Real phone verification (Firebase) is not wired up yet.
        </Text>
      ) : null}
    </Screen>
  );
}
