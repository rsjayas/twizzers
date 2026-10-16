import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { api } from '../api';
import type { Creation, MusicTrack, Poem, Template } from '../types';
import { Button, Card, ErrorText, Screen, colors } from '../ui';

export function StyleScreen({ poem, onCreated, onBack }: { poem: Poem; onCreated: (c: Creation) => void; onBack: () => void }) {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [tracks, setTracks] = useState<MusicTrack[] | null>(null);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [musicId, setMusicId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.templates(), api.music()])
      .then(([t, m]) => {
        setTemplates(t);
        setTracks(m);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load styles'));
  }, []);

  const create = async () => {
    if (!templateId || !musicId) return;
    setBusy(true);
    setError(null);
    try {
      onCreated(await api.createCreation(poem.id, templateId, musicId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen title="Choose the look and music" subtitle="Your poem becomes a short video.">
      {!templates || !tracks ? <ActivityIndicator color={colors.accent} /> : (
        <>
          <Text style={{ fontWeight: '700', color: colors.text, marginBottom: 8 }}>Style</Text>
          {templates.map((t) => (
            <Card key={t.id} selected={templateId === t.id} onPress={() => setTemplateId(t.id)}>
              <Text style={{ color: colors.text, fontSize: 16 }}>{t.name}</Text>
              <Text style={{ color: colors.muted, fontSize: 13 }}>{t.mood_tags.join(', ')}</Text>
            </Card>
          ))}
          <Text style={{ fontWeight: '700', color: colors.text, marginVertical: 8 }}>Music</Text>
          {tracks.map((m) => (
            <Card key={m.id} selected={musicId === m.id} onPress={() => setMusicId(m.id)}>
              <Text style={{ color: colors.text, fontSize: 16 }}>{m.title}</Text>
              <Text style={{ color: colors.muted, fontSize: 13 }}>{m.mood_tags.join(', ')}</Text>
            </Card>
          ))}
        </>
      )}
      <ErrorText message={error} />
      <Button label="Make my video" onPress={create} loading={busy} disabled={!templateId || !musicId} />
      <Button label="Back" onPress={onBack} secondary />
    </Screen>
  );
}
