import React, { useState } from 'react';
import { Linking, View } from 'react-native';
import { ApiError, api } from '../api';
import { auth } from '../auth';
import { CHECKOUT_URL, API_BASE } from '../config';
import type { Poem } from '../types';
import { Button, Chip, ErrorText, Field, Screen } from '../ui';

const OCCASIONS = ['anniversary', 'apology', 'gratitude', 'long_distance', 'birthday', 'just_because'];
const TONES = ['deeply_romantic', 'playful', 'nostalgic'];
const label = (s: string) => s.replace(/_/g, ' ');

export function CreateScreen({ onPoem }: { onPoem: (poem: Poem) => void }) {
  const [mode, setMode] = useState<'ai' | 'write'>('ai');
  const [occasion, setOccasion] = useState(OCCASIONS[0]);
  const [tone, setTone] = useState(TONES[0]);
  const [nickname, setNickname] = useState('');
  const [detail1, setDetail1] = useState('');
  const [detail2, setDetail2] = useState('');
  const [own, setOwn] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsCredits, setNeedsCredits] = useState(false);

  const go = async () => {
    setBusy(true);
    setError(null);
    setNeedsCredits(false);
    try {
      const poem =
        mode === 'ai'
          ? await api.generatePoem({
              occasion,
              tone,
              recipient_nickname: nickname || undefined,
              detail_1: detail1 || undefined,
              detail_2: detail2 || undefined,
            })
          : await api.writePoem(own.trim());
      onPoem(poem);
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) setNeedsCredits(true);
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  // Credits are bought on a web page opened in the phone's browser (not an
  // in-app WebView). The Firebase token goes in the URL fragment.
  const buyCredits = async () => {
    const token = await auth.getToken();
    if (!CHECKOUT_URL || !token) {
      setError('Buying credits is not available yet.');
      return;
    }
    Linking.openURL(`${CHECKOUT_URL}?api=${encodeURIComponent(API_BASE)}#token=${encodeURIComponent(token)}`);
  };

  return (
    <Screen title="Write your poem" subtitle="Let AI help, or write it yourself.">
      <View style={{ flexDirection: 'row', marginBottom: 16 }}>
        <Chip label="AI poem" selected={mode === 'ai'} onPress={() => setMode('ai')} />
        <Chip label="I'll write it" selected={mode === 'write'} onPress={() => setMode('write')} />
      </View>

      {mode === 'ai' ? (
        <>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
            {OCCASIONS.map((o) => <Chip key={o} label={label(o)} selected={o === occasion} onPress={() => setOccasion(o)} />)}
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginBottom: 8 }}>
            {TONES.map((t) => <Chip key={t} label={label(t)} selected={t === tone} onPress={() => setTone(t)} />)}
          </View>
          <Field label="What do you call them?" value={nickname} onChangeText={setNickname} placeholder="Jaan" />
          <Field label="A memory or detail (optional)" value={detail1} onChangeText={setDetail1} placeholder="We met in the rain" />
          <Field label="Another detail (optional)" value={detail2} onChangeText={setDetail2} />
        </>
      ) : (
        <Field label="Your poem" value={own} onChangeText={setOwn} multiline placeholder={'One line per row…'} />
      )}

      <ErrorText message={error} />
      {needsCredits && CHECKOUT_URL ? <Button label="Buy credits" onPress={buyCredits} secondary /> : null}
      <Button
        label={mode === 'ai' ? 'Generate poems' : 'Continue'}
        onPress={go}
        loading={busy}
        disabled={mode === 'write' && own.trim().length < 4}
      />
    </Screen>
  );
}
