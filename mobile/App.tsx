import { StatusBar } from 'expo-status-bar';
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, AppState, Linking, Text, View } from 'react-native';
import { api } from './src/api';
import { auth } from './src/auth';
import { AccountScreen } from './src/screens/AccountScreen';
import { CreateScreen } from './src/screens/CreateScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { PickPoemScreen } from './src/screens/PickPoemScreen';
import { ResultScreen } from './src/screens/ResultScreen';
import { StyleScreen } from './src/screens/StyleScreen';
import { VideosScreen } from './src/screens/VideosScreen';
import type { AppConfig, Creation, Poem, User } from './src/types';

// A small state machine instead of a navigation library: login -> create ->
// (pick variant) -> style -> result.
type Step =
  | { name: 'login' }
  | { name: 'create' }
  | { name: 'videos' }
  | { name: 'account' }
  | { name: 'pick'; poem: Poem }
  | { name: 'style'; poem: Poem }
  | { name: 'result'; poem: Poem; creation: Creation };

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [credits, setCredits] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [step, setStep] = useState<Step>({ name: 'login' });
  const [restoring, setRestoring] = useState(true);

  const refreshCredits = useCallback(() => {
    api.balance().then((b) => setCredits(b.credits_balance)).catch(() => {});
  }, []);

  // What the server charges and whether sign-ups are open (no login needed).
  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
  }, []);

  // Credits are bought on a web page in the phone's browser, which sends the user back with
  // tweezers://credits-success. Refresh the balance on that link, and whenever the app comes back to the front.
  useEffect(() => {
    const onUrl = (url: string | null) => {
      if (url?.startsWith('tweezers://credits-success')) {
        refreshCredits();
        setNotice('Credits added. Thank you!');
      }
    };
    Linking.getInitialURL().then(onUrl).catch(() => {});
    const linkSub = Linking.addEventListener('url', (e) => onUrl(e.url));
    const stateSub = AppState.addEventListener('change', (state) => state === 'active' && user && refreshCredits());
    return () => {
      linkSub.remove();
      stateSub.remove();
    };
  }, [user, refreshCredits]);

  useEffect(() => {
    if (user) refreshCredits();
  }, [user, refreshCredits]);

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
          config={config}
          credits={credits}
          onVideos={() => setStep({ name: 'videos' })}
          onAccount={() => setStep({ name: 'account' })}
          onCreditsChanged={refreshCredits}
        />
      );
      break;
    case 'videos':
      screen = <VideosScreen onBack={() => setStep({ name: 'create' })} />;
      break;
    case 'account':
      screen = user ? (
        <AccountScreen
          user={user}
          onBack={() => setStep({ name: 'create' })}
          onSignedOut={() => { setUser(null); setCredits(null); setStep({ name: 'login' }); }}
        />
      ) : <LoginScreen onSignedIn={(u) => { setUser(u); setStep({ name: 'create' }); }} />;
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
      {notice ? (
        <View style={{ position: 'absolute', top: 48, left: 20, right: 20, backgroundColor: '#3a1f2b', padding: 12, borderRadius: 12 }}>
          <Text style={{ color: '#fff' }} onPress={() => setNotice(null)}>{notice}  (tap to close)</Text>
        </View>
      ) : null}
      <StatusBar style="dark" />
    </>
  );
}
