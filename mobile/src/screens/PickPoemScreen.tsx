import React, { useState } from 'react';
import { Text } from 'react-native';
import { api } from '../api';
import type { Poem } from '../types';
import { Button, Card, ErrorText, Screen, colors } from '../ui';

// AI poems arrive as 3 variants to choose from; a poem the user wrote is
// already final and skips this screen.
export function PickPoemScreen({ poem, onChosen, onBack }: { poem: Poem; onChosen: (poem: Poem) => void; onBack: () => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      onChosen(await api.selectVariant(poem.id, selected));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen title="Pick your favourite" subtitle="Tap the one that feels most like you.">
      {poem.variants.map((v) => (
        <Card key={v.id} selected={selected === v.id} onPress={() => setSelected(v.id)}>
          <Text style={{ color: colors.text, fontSize: 16, lineHeight: 24 }}>{v.variant_text}</Text>
        </Card>
      ))}
      <ErrorText message={error} />
      <Button label="Use this poem" onPress={confirm} loading={busy} disabled={!selected} />
      <Button label="Back" onPress={onBack} secondary />
    </Screen>
  );
}
