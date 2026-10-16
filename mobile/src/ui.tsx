import React from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

export const colors = { bg: '#fff0f4', card: '#ffffff', accent: '#d1416b', text: '#3a1f2b', muted: '#8a6070', border: '#f4dbe4' };

export function Screen({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.screenContent} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      {children}
    </ScrollView>
  );
}

export function Button({ label, onPress, disabled, loading, secondary }: {
  label: string; onPress: () => void; disabled?: boolean; loading?: boolean; secondary?: boolean;
}) {
  const off = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={off}
      style={[styles.button, secondary && styles.buttonSecondary, off && styles.buttonOff]}
    >
      {loading ? <ActivityIndicator color={secondary ? colors.accent : '#fff'} /> : (
        <Text style={[styles.buttonText, secondary && { color: colors.accent }]}>{label}</Text>
      )}
    </Pressable>
  );
}

export function Field({ label, ...props }: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={{ marginBottom: 14 }}>
      <Text style={styles.label}>{label}</Text>
      <TextInput placeholderTextColor="#c9a3b1" {...props} style={[styles.input, props.multiline && { minHeight: 120, textAlignVertical: 'top' }]} />
    </View>
  );
}

export function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, selected && styles.chipOn]}>
      <Text style={[styles.chipText, selected && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

export function Card({ selected, onPress, children }: { selected?: boolean; onPress?: () => void; children: React.ReactNode }) {
  return (
    <Pressable onPress={onPress} style={[styles.card, selected && styles.cardOn]}>
      {children}
    </Pressable>
  );
}

export function ErrorText({ message }: { message: string | null }) {
  return message ? <Text style={styles.error}>{message}</Text> : null;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  screenContent: { padding: 20, paddingTop: 56, paddingBottom: 40 },
  title: { fontSize: 26, fontWeight: '700', color: colors.text, marginBottom: 4 },
  subtitle: { fontSize: 15, color: colors.muted, marginBottom: 20 },
  button: { backgroundColor: colors.accent, borderRadius: 28, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  buttonSecondary: { backgroundColor: 'transparent', borderWidth: 2, borderColor: colors.accent },
  buttonOff: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  label: { fontSize: 13, color: colors.muted, marginBottom: 6 },
  input: { backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 12, fontSize: 16, color: colors.text },
  chip: { borderWidth: 2, borderColor: colors.border, borderRadius: 20, paddingVertical: 8, paddingHorizontal: 14, marginRight: 8, marginBottom: 8, backgroundColor: colors.card },
  chipOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.text, fontSize: 14 },
  card: { backgroundColor: colors.card, borderRadius: 14, borderWidth: 2, borderColor: colors.border, padding: 16, marginBottom: 12 },
  cardOn: { borderColor: colors.accent, backgroundColor: '#fff7f9' },
  error: { color: '#b3261e', marginVertical: 8 },
});
