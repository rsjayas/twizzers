import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { EmailNotVerifiedError, auth, friendlyError } from '../auth';
import { AUTH_MODE } from '../config';
import type { User } from '../types';
import { Button, ErrorText, Field, Screen, colors } from '../ui';

type Mode = 'signin' | 'signup' | 'verify' | 'reset' | 'phone' | 'phoneCode';

const looksLikeEmail = (s: string) => /^\S+@\S+\.\S+$/.test(s.trim());

export function LoginScreen({ onSignedIn }: { onSignedIn: (user: User) => void }) {
  const [mode, setMode] = useState<Mode>('signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const go = (next: Mode) => {
    setMode(next);
    setError(null);
    setInfo(null);
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await fn();
    } catch (e) {
      if (e instanceof EmailNotVerifiedError) {
        setMode('verify');
        setInfo(e.message);
      } else {
        setError(friendlyError(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const signIn = () => run(async () => onSignedIn(await auth.signInWithEmail(email, password)));

  const signUp = () =>
    run(async () => {
      await auth.signUpWithEmail({ name, email, password });
      setMode('verify');
      setInfo(`We sent a confirmation link to ${email.trim()}.`);
    });

  const checkVerified = () => run(async () => onSignedIn(await auth.checkVerified()));

  const resend = () =>
    run(async () => {
      await auth.resendVerification();
      setInfo('Sent again. Check your inbox and spam folder.');
    });

  const sendReset = () =>
    run(async () => {
      await auth.sendPasswordReset(email);
      setInfo('If that email has an account, a reset link is on its way.');
    });

  const google = () =>
    run(async () => {
      const user = await auth.signInWithGoogle();
      if (user) onSignedIn(user);
    });

  const sendPhoneCode = () =>
    run(async () => {
      await auth.sendPhoneCode(phone);
      setMode('phoneCode');
    });
  const verifyPhone = () => run(async () => onSignedIn(await auth.verifyPhoneCode({ name, code })));

  const emailOk = looksLikeEmail(email);

  return (
    <Screen title="Tweezers" subtitle="Two bodies, one soul. Turn your feelings into a poem they'll keep.">
      {mode === 'signin' || mode === 'signup' ? (
        <>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 12 }}>
            {mode === 'signin' ? 'Sign in' : 'Create your account'}
          </Text>
          {mode === 'signup' ? <Field label="Your name" value={name} onChangeText={setName} placeholder="Asha" autoCapitalize="words" /> : null}
          <Field label="Email" value={email} onChangeText={setEmail} placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
          <Field label="Password" value={password} onChangeText={setPassword} placeholder="At least 8 characters" secureTextEntry autoCapitalize="none" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
          <ErrorText message={error} />
          <Button
            label={mode === 'signin' ? 'Sign in' : 'Create account'}
            onPress={mode === 'signin' ? signIn : signUp}
            loading={busy}
            disabled={!emailOk || password.length < 8 || (mode === 'signup' && name.trim().length < 1)}
          />
          {mode === 'signin' ? (
            <Pressable onPress={() => go('reset')} style={{ marginTop: 14 }}>
              <Text style={{ color: colors.accent, textAlign: 'center' }}>Forgot password?</Text>
            </Pressable>
          ) : null}
          <Pressable onPress={() => go(mode === 'signin' ? 'signup' : 'signin')} style={{ marginTop: 14 }}>
            <Text style={{ color: colors.accent, textAlign: 'center' }}>
              {mode === 'signin' ? 'New here? Create an account' : 'Already have an account? Sign in'}
            </Text>
          </Pressable>

          {auth.methods.google || auth.methods.phone ? (
            <View style={{ marginTop: 22 }}>
              <Text style={{ color: colors.muted, textAlign: 'center', marginBottom: 8 }}>or</Text>
              {auth.methods.google ? <Button label="Continue with Google" onPress={google} loading={busy} secondary /> : null}
              {auth.methods.phone ? <Button label="Use phone number" onPress={() => go('phone')} secondary /> : null}
            </View>
          ) : null}
        </>
      ) : null}

      {mode === 'verify' ? (
        <>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 8 }}>Confirm your email</Text>
          <Text style={{ color: colors.muted, marginBottom: 12 }}>
            Open the link we emailed to {email.trim() || 'you'}, then come back and tap the button below.
          </Text>
          {info ? <Text style={{ color: colors.text, marginBottom: 8 }}>{info}</Text> : null}
          <ErrorText message={error} />
          <Button label="I've confirmed my email" onPress={checkVerified} loading={busy} />
          <Button label="Send the email again" onPress={resend} secondary disabled={busy} />
          <Pressable onPress={() => go('signin')} style={{ marginTop: 14 }}>
            <Text style={{ color: colors.accent, textAlign: 'center' }}>Back to sign in</Text>
          </Pressable>
        </>
      ) : null}

      {mode === 'reset' ? (
        <>
          <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 8 }}>Reset your password</Text>
          <Field label="Email" value={email} onChangeText={setEmail} placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" />
          {info ? <Text style={{ color: colors.text, marginBottom: 8 }}>{info}</Text> : null}
          <ErrorText message={error} />
          <Button label="Send reset link" onPress={sendReset} loading={busy} disabled={!emailOk} />
          <Pressable onPress={() => go('signin')} style={{ marginTop: 14 }}>
            <Text style={{ color: colors.accent, textAlign: 'center' }}>Back to sign in</Text>
          </Pressable>
        </>
      ) : null}

      {mode === 'phone' ? (
        <>
          <Field label="Phone number" value={phone} onChangeText={setPhone} placeholder="+91 98765 43210" keyboardType="phone-pad" />
          <ErrorText message={error} />
          <Button label="Send code" onPress={sendPhoneCode} loading={busy} disabled={phone.trim().length < 8} />
          <Button label="Back" onPress={() => go('signin')} secondary />
        </>
      ) : null}

      {mode === 'phoneCode' ? (
        <>
          <Text style={{ color: colors.muted, marginBottom: 12 }}>We sent a 6-digit code to {phone.trim()}.</Text>
          <Field label="Code" value={code} onChangeText={setCode} placeholder="123456" keyboardType="number-pad" maxLength={6} />
          <ErrorText message={error} />
          <Button label="Verify" onPress={verifyPhone} loading={busy} disabled={code.trim().length < 6} />
          <Button label="Use a different number" onPress={() => go('phone')} secondary />
        </>
      ) : null}

      {AUTH_MODE === 'dev' ? (
        <Text style={{ color: colors.muted, marginTop: 24, fontSize: 12 }}>
          Dev login: passwords and emails are not checked. Set EXPO_PUBLIC_AUTH_MODE=firebase for real accounts.
        </Text>
      ) : null}
    </Screen>
  );
}
