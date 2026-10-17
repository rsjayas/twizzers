import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Share, Text, View } from 'react-native';
import { api } from '../api';
import { SHARE_BASE } from '../config';
import type { MyCreation } from '../types';
import { Button, Card, ErrorText, Screen, colors } from '../ui';

const statusLabel = { rendering: 'Making your video…', ready: 'Ready', failed: 'Could not be made' } as const;

export function VideosScreen({ onBack }: { onBack: () => void }) {
  const [items, setItems] = useState<MyCreation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.myCreations().then(setItems).catch((e) => setError(e instanceof Error ? e.message : 'Could not load'));
  useEffect(() => {
    load();
  }, []);

  const link = (c: MyCreation) => `${SHARE_BASE}/v/${c.share_link_slug}`;
  const share = (c: MyCreation) =>
    Share.share({ message: `I made this for you 💌\n${link(c)}` })
      .then((r) => { if (r.action === Share.sharedAction) api.logShare(c.id, 'link').catch(() => {}); })
      .catch(() => {});

  return (
    <Screen title="My videos" subtitle="Everything you have made.">
      {!items && !error ? <ActivityIndicator color={colors.accent} /> : null}
      <ErrorText message={error} />
      {items && items.length === 0 ? <Text style={{ color: colors.muted }}>Nothing yet. Make your first poem!</Text> : null}
      {items?.map((c) => (
        <Card key={c.id}>
          <Text style={{ color: colors.text, fontSize: 16, lineHeight: 24 }} numberOfLines={4}>{c.poem ?? '(poem)'}</Text>
          <Text style={{ color: colors.muted, fontSize: 13, marginTop: 6 }}>
            {statusLabel[c.status]}{c.created_at ? ` · ${new Date(c.created_at + 'Z').toLocaleDateString()}` : ''}
          </Text>
          {c.status === 'ready' ? (
            <View style={{ marginTop: 6 }}>
              <Button label="Share" onPress={() => share(c)} />
              <Button label="Open" onPress={() => Linking.openURL(link(c))} secondary />
            </View>
          ) : null}
          {c.status === 'rendering' ? <Button label="Refresh" onPress={load} secondary /> : null}
        </Card>
      ))}
      <Button label="Back" onPress={onBack} secondary />
    </Screen>
  );
}
