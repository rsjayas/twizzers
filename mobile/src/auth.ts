import { API_BASE, AUTH_MODE } from './config';
import type { User } from './types';

// The rest of the app only needs "who is signed in" and "a bearer token".
export interface AuthProvider {
  /** Dev mode: name + phone. Firebase mode: phone, then confirmOtp(code). */
  signIn(input: { name: string; phone: string }): Promise<User>;
  getToken(): Promise<string | null>;
  signOut(): Promise<void>;
}

// Local demo login. Needs the backend running with AUTH_DEV_BYPASS=true, which
// accepts "Bearer dev:<user_id>". Never ship this to production.
class DevAuth implements AuthProvider {
  private user: User | null = null;

  async signIn({ name, phone }: { name: string; phone: string }): Promise<User> {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone }),
    });
    if (!res.ok) {
      throw new Error('Login failed. Is the backend running with AUTH_DEV_BYPASS=true?');
    }
    this.user = (await res.json()) as User;
    return this.user;
  }

  async getToken() {
    return this.user ? `dev:${this.user.id}` : null;
  }

  async signOut() {
    this.user = null;
  }
}

// TODO(firebase): real phone-OTP login. Needs a Firebase project, a development
// build (not Expo Go) with the native Firebase auth module, and these steps:
//   1. send an OTP to the phone number,
//   2. confirm the code to get a Firebase user,
//   3. user.getIdToken() is the bearer token,
//   4. POST {id_token} to /auth/firebase to get the backend user.
// Then implement this class and set EXPO_PUBLIC_AUTH_MODE=firebase.
class FirebaseAuth implements AuthProvider {
  async signIn(): Promise<User> {
    throw new Error('Firebase login is not implemented yet.');
  }
  async getToken(): Promise<string | null> {
    return null;
  }
  async signOut() {}
}

export const auth: AuthProvider = AUTH_MODE === 'firebase' ? new FirebaseAuth() : new DevAuth();
