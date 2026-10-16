// The native Firebase module is loaded lazily so dev mode still works in Expo Go
// (which does not contain it). Firebase mode needs a development build.
const firebase = () => import('@react-native-firebase/auth');
import type { ConfirmationResult } from '@react-native-firebase/auth';
import { API_BASE, AUTH_MODE } from './config';
import type { User } from './types';

// The rest of the app only needs "who is signed in" and "a bearer token".
export interface AuthProvider {
  /** true: the user must enter an SMS code (sendCode, then verify). */
  requiresOtp: boolean;
  /** Already signed in from an earlier run? Returns the backend user. */
  restore(): Promise<User | null>;
  sendCode(phone: string): Promise<void>;
  verify(input: { name: string; phone: string; code: string }): Promise<User>;
  getToken(): Promise<string | null>;
  signOut(): Promise<void>;
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
  if (!res.ok) throw new Error(`Login failed (${res.status})`);
  return (await res.json()) as T;
}

// Local demo login. Needs the backend running with AUTH_DEV_BYPASS=true, which
// accepts "Bearer dev:<user_id>". Never ship this to production.
class DevAuth implements AuthProvider {
  requiresOtp = false;
  private user: User | null = null;

  async restore() {
    return null;
  }
  async sendCode() {}
  async verify({ name, phone }: { name: string; phone: string; code: string }) {
    try {
      this.user = await postJson<User>('/auth/signup', { name, phone });
    } catch {
      throw new Error('Login failed. Is the backend running with AUTH_DEV_BYPASS=true?');
    }
    return this.user;
  }
  async getToken() {
    return this.user ? `dev:${this.user.id}` : null;
  }
  async signOut() {
    this.user = null;
  }
}

// Real phone-OTP login with Firebase Auth. Needs a development build (native
// module), not Expo Go. Flow: SMS code -> Firebase user -> ID token -> the
// backend verifies it at POST /auth/firebase and returns/creates the user.
class FirebaseAuth implements AuthProvider {
  requiresOtp = true;
  private confirmation: ConfirmationResult | null = null;

  private async backendUser(name?: string): Promise<User> {
    const token = await this.getToken();
    if (!token) throw new Error('Not signed in');
    return postJson<User>('/auth/firebase', { id_token: token, name: name || undefined });
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
      return null; // offline or token rejected: just show the login screen
    }
  }

  async sendCode(phone: string) {
    // E.164 format, e.g. +919876543210. Bare 10-digit numbers are assumed Indian.
    const { getAuth, signInWithPhoneNumber } = await firebase();
    const digits = phone.replace(/[^\d+]/g, '');
    const e164 = digits.startsWith('+') ? digits : `+91${digits.replace(/^0+/, '')}`;
    this.confirmation = await signInWithPhoneNumber(getAuth(), e164);
  }

  async verify({ name, code }: { name: string; phone: string; code: string }) {
    if (!this.confirmation) throw new Error('Request a code first.');
    await this.confirmation.confirm(code.trim());
    return this.backendUser(name.trim());
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
  }
}

export const auth: AuthProvider = AUTH_MODE === 'firebase' ? new FirebaseAuth() : new DevAuth();
