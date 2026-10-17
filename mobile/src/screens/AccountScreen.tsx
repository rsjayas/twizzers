import React, { useState } from 'react';
import { Linking, Pressable, Text } from 'react-native';
import { api } from '../api';
import { auth, friendlyError } from '../auth';
import { API_BASE } from '../config';
import type { User } from '../types';
import { Button, Card, ErrorText, Field, Screen, colors } from '../ui';

export function AccountScreen({ user, onBack, onSignedOut }: { user: User; onBack: () => void; onSignedOut: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const signOut = async () => {
    await auth.signOut();
    onSignedOut();
  };

  const deleteAccount = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.eraseMe(); // poems, videos and sign-in links on our servers
      await auth.deleteAccount(); // the sign-in account itself
      await auth.signOut();
      onSignedOut();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen title="My account">
      <Card>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: '700' }}>{user.name || 'Your account'}</Text>
        <Text style={{ color: colors.muted }}>{user.email || user.phone || ''}</Text>
      </Card>

      <Button label="Sign out" onPress={signOut} />
      <Pressable onPress={() => Linking.openURL(`${API_BASE}/privacy`)} style={{ marginTop: 18 }}>
        <Text style={{ color: colors.accent, textAlign: 'center' }}>Privacy policy</Text>
      </Pressable>
      <Pressable onPress={() => Linking.openURL(`${API_BASE}/terms`)} style={{ marginTop: 10 }}>
        <Text style={{ color: colors.accent, textAlign: 'center' }}>Terms of use</Text>
      </Pressable>

      <Text style={{ marginTop: 28, fontWeight: '700', color: colors.text }}>Delete my account</Text>
      {!confirming ? (
        <>
          <Text style={{ color: colors.muted, marginVertical: 8 }}>
            Removes your poems, videos and sharing links, and your login. Links you shared stop working. This cannot be undone.
          </Text>
          <Button label="Delete my account…" onPress={() => setConfirming(true)} secondary />
        </>
      ) : (
        <>
          <Text style={{ color: colors.muted, marginVertical: 8 }}>Type DELETE to confirm.</Text>
          <Field label="Confirmation" value={typed} onChangeText={setTyped} autoCapitalize="characters" placeholder="DELETE" />
          <ErrorText message={error} />
          <Button label="Permanently delete" onPress={deleteAccount} loading={busy} disabled={typed !== 'DELETE'} />
          <Button label="Cancel" onPress={() => { setConfirming(false); setTyped(''); setError(null); }} secondary />
        </>
      )}
      <Button label="Back" onPress={onBack} secondary />
    </Screen>
  );
}
