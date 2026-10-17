// The native Firebase and Google modules are loaded lazily so dev mode still works in Expo Go
// (which does not contain them). Firebase mode needs a development build.
const firebase = () => import('@react-native-firebase/auth');
const googleSignin = () => import('@react-native-google-signin/google-signin');
import type { ConfirmationResult } from '@react-native-firebase/auth';
import { API_BASE, AUTH_MODE, ENABLE_PHONE_LOGIN, GOOGLE_WEB_CLIENT_ID } from './config';
import type { User } from './types';

/** Thrown when an email + password account has not confirmed its email yet. */
export class EmailNotVerifiedError extends Error {
  constructor(public email: string) {
    super('Please confirm your email address first.');
  }
}

// What the rest of the app needs: who is signed in, and a bearer token for the API.
export interface AuthProvider {
  /** Which sign-in methods to show. */
  methods: { email: true; google: boolean; phone: boolean };
  /** Already signed in from an earlier run? Returns the backend user. */
  restore(): Promise<User | null>;
  /** Creates the account and sends a verification email. Follow with checkVerified(). */
  signUpWithEmail(input: { name: string; email: string; password: string }): Promise<void>;
  /** Throws EmailNotVerifiedError if the address is not confirmed yet. */
  signInWithEmail(email: string, password: string): Promise<User>;
  /** After the user opened the link in the verification email. */
  checkVerified(): Promise<User>;
  resendVerification(): Promise<void>;
  sendPasswordReset(email: string): Promise<void>;
  /** null when the user cancelled the Google dialog. */
  signInWithGoogle(): Promise<User | null>;
  // Phone (SMS) login: built, hidden unless ENABLE_PHONE_LOGIN.
  sendPhoneCode(phone: string): Promise<void>;
  verifyPhoneCode(input: { name: string; code: string }): Promise<User>;
  getToken(): Promise<string | null>;
  signOut(): Promise<void>;
  /** Deletes the sign-in account itself (after the backend erased the data). */
  deleteAccount(): Promise<void>;
}

async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('Cannot reach the server. Check your connection.');
  }
  if (!res.ok) {
    let detail = '';
    try {
      detail = (await res.json()).detail ?? '';
    } catch {}
    if (detail === 'email_not_verified') throw new Error('email_not_verified');
    if (detail === 'signups_closed') throw new Error('New accounts are closed right now. Please try again later.');
    if (detail === 'account_blocked') throw new Error('This account has been blocked. Contact support if you think this is a mistake.');
    throw new Error(`Login failed (${res.status})`);
  }
  return (await res.json()) as T;
}

/** Turns Firebase error codes into sentences a person can act on. */
export function friendlyError(e: unknown): string {
  const code = (e as { code?: string })?.code ?? '';
  const known: Record<string, string> = {
    'auth/invalid-email': 'That email address does not look right.',
    'auth/email-already-in-use': 'An account with this email already exists. Try signing in instead.',
    'auth/weak-password': 'Choose a stronger password (at least 8 characters).',
    'auth/invalid-credential': 'Wrong email or password.',
    'auth/wrong-password': 'Wrong email or password.',
    'auth/user-not-found': 'Wrong email or password.',
    'auth/too-many-requests': 'Too many attempts. Wait a few minutes and try again.',
    'auth/network-request-failed': 'No connection. Check your internet and try again.',
    'auth/user-disabled': 'This account has been disabled.',
    'auth/requires-recent-login': 'For safety, please sign in again and then retry.',
    'auth/invalid-verification-code': 'That code is not correct.',
    'auth/account-exists-with-different-credential': 'This email is already registered with another sign-in method.',
  };
  if (known[code]) return known[code];
  if (e instanceof Error && e.message === 'email_not_verified') return 'Please confirm your email address first.';
  return e instanceof Error ? e.message : 'Something went wrong. Please try again.';
}

// Local demo login. Needs the backend running with AUTH_DEV_BYPASS=true, which accepts
// "Bearer dev:<user_id>". No passwords or emails are checked. Never ship this to production.
class DevAuth implements AuthProvider {
  methods = { email: true as const, google: false, phone: false };
  private user: User | null = null;

  async restore() {
    return null;
  }
  private async devLogin(body: { email?: string; name?: string; phone?: string }) {
    try {
      this.user = await postJson<User>('/auth/signup', body);
    } catch {
      throw new Error('Login failed. Is the backend running with AUTH_DEV_BYPASS=true?');
    }
    return this.user;
  }
  async signUpWithEmail({ name, email }: { name: string; email: string; password: string }) {
    await this.devLogin({ name, email });
  }
  async signInWithEmail(email: string) {
    return this.devLogin({ email });
  }
  async checkVerified() {
    if (!this.user) throw new Error('Not signed in');
    return this.user;
  }
  async resendVerification() {}
  async sendPasswordReset() {
    throw new Error('Password reset is not available in dev mode.');
  }
  async signInWithGoogle(): Promise<User | null> {
    throw new Error('Google sign-in needs Firebase mode.');
  }
  async sendPhoneCode() {}
  async verifyPhoneCode({ name }: { name: string; code: string }) {
    return this.devLogin({ name, phone: '+910000000000' });
  }
  async getToken() {
    return this.user ? `dev:${this.user.id}` : null;
  }
  async signOut() {
    this.user = null;
  }
  async deleteAccount() {
    this.user = null;
  }
}

// Real login with Firebase Auth: email + password (primary), Google, phone. After any of
// them, the Firebase ID token goes to POST /auth/firebase, and the backend returns (or
// creates) the user and links sign-in methods that share a verified email.
class FirebaseAuth implements AuthProvider {
  methods = { email: true as const, google: Boolean(GOOGLE_WEB_CLIENT_ID), phone: ENABLE_PHONE_LOGIN };
  private confirmation: ConfirmationResult | null = null;

  private async backendUser(): Promise<User> {
    const token = await this.getToken();
    if (!token) throw new Error('Not signed in');
    return postJson<User>('/auth/firebase', { id_token: token }, undefined);
  }

  async restore() {
    // Firebase keeps the session between app launches; wait for it to load.
    const { getAuth, onAuthStateChanged } = await firebase();
    const firebaseUser = await new Promise<unknown>((resolve) => {
      const unsubscribe = onAuthStateChanged(getAuth(), (u) => {
        unsubscribe();
        resolve(u);
      });
    });
    if (!firebaseUser) return null;
    try {
      return await this.backendUser();
    } catch {
      return null; // offline, or email not verified yet: show the login screen
    }
  }

  async signUpWithEmail({ name, email, password }: { name: string; email: string; password: string }) {
    const { getAuth, createUserWithEmailAndPassword, updateProfile, sendEmailVerification } = await firebase();
    const cred = await createUserWithEmailAndPassword(getAuth(), email.trim(), password);
    if (name.trim()) await updateProfile(cred.user, { displayName: name.trim() });
    await sendEmailVerification(cred.user);
  }

  async signInWithEmail(email: string, password: string) {
    const { getAuth, signInWithEmailAndPassword } = await firebase();
    const cred = await signInWithEmailAndPassword(getAuth(), email.trim(), password);
    if (!cred.user.emailVerified) throw new EmailNotVerifiedError(email.trim());
    return this.backendUser();
  }

  async checkVerified() {
    const { getAuth, reload, getIdToken } = await firebase();
    const user = getAuth().currentUser;
    if (!user) throw new Error('Please sign in again.');
    await reload(user);
    if (!user.emailVerified) throw new EmailNotVerifiedError(user.email ?? '');
    await getIdToken(user, true); // refresh so the token says the email is verified
    return this.backendUser();
  }

  async resendVerification() {
    const { getAuth, sendEmailVerification } = await firebase();
    const user = getAuth().currentUser;
    if (!user) throw new Error('Please sign in again.');
    await sendEmailVerification(user);
  }

  async sendPasswordReset(email: string) {
    const { getAuth, sendPasswordResetEmail } = await firebase();
    await sendPasswordResetEmail(getAuth(), email.trim());
  }

  async signInWithGoogle(): Promise<User | null> {
    if (!GOOGLE_WEB_CLIENT_ID) throw new Error('Google sign-in is not configured.');
    const { GoogleSignin } = await googleSignin();
    const { getAuth, GoogleAuthProvider, signInWithCredential } = await firebase();
    GoogleSignin.configure({ webClientId: GOOGLE_WEB_CLIENT_ID });
    await GoogleSignin.hasPlayServices();
    const res = await GoogleSignin.signIn();
    if (res.type !== 'success') return null; // cancelled
    const idToken = res.data.idToken;
    if (!idToken) throw new Error('Google did not return a token. Try again.');
    await signInWithCredential(getAuth(), GoogleAuthProvider.credential(idToken));
    return this.backendUser();
  }

  async sendPhoneCode(phone: string) {
    // E.164 format, e.g. +919876543210. Bare 10-digit numbers are assumed Indian.
    const { getAuth, signInWithPhoneNumber } = await firebase();
    const digits = phone.replace(/[^\d+]/g, '');
    const e164 = digits.startsWith('+') ? digits : `+91${digits.replace(/^0+/, '')}`;
    this.confirmation = await signInWithPhoneNumber(getAuth(), e164);
  }

  async verifyPhoneCode({ code }: { name: string; code: string }) {
    if (!this.confirmation) throw new Error('Request a code first.');
    await this.confirmation.confirm(code.trim());
    return this.backendUser();
  }

  async getToken() {
    const { getAuth, getIdToken } = await firebase();
    const user = getAuth().currentUser;
    // Firebase refreshes the ID token automatically when it is close to expiry.
    return user ? getIdToken(user) : null;
  }

  async signOut() {
    this.confirmation = null;
    const { getAuth, signOut } = await firebase();
    await signOut(getAuth());
    try {
      const { GoogleSignin } = await googleSignin();
      await GoogleSignin.signOut();
    } catch {
      // not signed in with Google, or the module is unavailable
    }
  }

  async deleteAccount() {
    const { getAuth, deleteUser } = await firebase();
    const user = getAuth().currentUser;
    if (!user) return;
    try {
      await deleteUser(user);
    } catch (e) {
      if ((e as { code?: string })?.code === 'auth/requires-recent-login') {
        throw new Error('Your videos and data are deleted. To finish removing your login, sign in again and delete once more.');
      }
      throw e;
    }
  }
}

export const auth: AuthProvider = AUTH_MODE === 'firebase' ? new FirebaseAuth() : new DevAuth();
