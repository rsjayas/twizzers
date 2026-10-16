import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { auth } from './src/auth';
import { CreateScreen } from './src/screens/CreateScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { PickPoemScreen } from './src/screens/PickPoemScreen';
import { ResultScreen } from './src/screens/ResultScreen';
import { StyleScreen } from './src/screens/StyleScreen';
import type { Creation, Poem, User } from './src/types';

// A small state machine instead of a navigation library: login -> create ->
// (pick variant) -> style -> result.
type Step =
  | { name: 'login' }
  | { name: 'create' }
  | { name: 'pick'; poem: Poem }
  | { name: 'style'; poem: Poem }
  | { name: 'result'; poem: Poem; creation: Creation };

export default function App() {
  const [, setUser] = useState<User | null>(null);
  const [step, setStep] = useState<Step>({ name: 'login' });
  const [restoring, setRestoring] = useState(true);

  // Returning users (Firebase keeps the session) skip the login screen.
  useEffect(() => {
    auth
      .restore()
      .then((u) => {
        if (u) {
          setUser(u);
          setStep({ name: 'create' });
        }
      })
      .catch(() => {})
      .finally(() => setRestoring(false));
  }, []);

  if (restoring) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff0f4' }}>
        <ActivityIndicator color="#d1416b" size="large" />
      </View>
    );
  }

  let screen: React.ReactElement;
  switch (step.name) {
    case 'login':
      screen = <LoginScreen onSignedIn={(u) => { setUser(u); setStep({ name: 'create' }); }} />;
      break;
    case 'create':
      screen = (
        <CreateScreen
          onPoem={(poem) => setStep(poem.status === 'finalized' ? { name: 'style', poem } : { name: 'pick', poem })}
        />
      );
      break;
    case 'pick':
      screen = (
        <PickPoemScreen
          poem={step.poem}
          onChosen={(poem) => setStep({ name: 'style', poem })}
          onBack={() => setStep({ name: 'create' })}
        />
      );
      break;
    case 'style':
      screen = (
        <StyleScreen
          poem={step.poem}
          onCreated={(creation) => setStep({ name: 'result', poem: step.poem, creation })}
          onBack={() => setStep({ name: 'create' })}
        />
      );
      break;
    case 'result':
      screen = <ResultScreen initial={step.creation} poem={step.poem} onAgain={() => setStep({ name: 'create' })} />;
      break;
  }

  return (
    <>
      {screen}
      <StatusBar style="dark" />
    </>
  );
}
