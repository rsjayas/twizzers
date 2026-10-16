import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Share, Text } from 'react-native';
import { api } from '../api';
import { SHARE_BASE } from '../config';
import type { Creation, Poem } from '../types';
import { Button, ErrorText, Screen, colors } from '../ui';

const POLL_MS = 3000;

export function ResultScreen({ initial, poem, onAgain }: { initial: Creation; poem: Poem; onAgain: () => void }) {
  const [creation, setCreation] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  // Rendering takes a while; poll until the render service reports back.
  useEffect(() => {
    if (creation.status !== 'rendering') return;
    const timer = setInterval(async () => {
      try {
        setCreation(await api.getCreation(creation.id));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not check status');
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [creation.id, creation.status]);

  const link = `${SHARE_BASE}/v/${creation.share_link_slug}`;

  const share = async () => {
    try {
      const result = await Share.share({ message: `I made this for you 💌\n${link}` });
      if (result.action === Share.sharedAction) api.logShare(creation.id, 'link').catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not share');
    }
  };

  return (
    <Screen
      title={creation.status === 'ready' ? 'Your poem is ready 💌' : creation.status === 'failed' ? 'Something went wrong' : 'Making your video…'}
      subtitle={creation.status === 'rendering' ? 'This usually takes a minute or two.' : undefined}
    >
      {creation.status === 'rendering' ? <ActivityIndicator color={colors.accent} size="large" /> : null}
      {poem.content ? <Text style={{ color: colors.text, fontSize: 17, lineHeight: 26, marginVertical: 16 }}>{poem.content}</Text> : null}
      <ErrorText message={error} />
      {creation.status === 'ready' ? <Button label="Share with them" onPress={share} /> : null}
      {creation.status === 'failed' ? <Text style={{ color: colors.muted }}>The video could not be made. You can try again.</Text> : null}
      <Button label="Make another" onPress={onAgain} secondary />
    </Screen>
  );
}
