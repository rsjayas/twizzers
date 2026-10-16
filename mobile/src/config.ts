// Public (EXPO_PUBLIC_*) settings, inlined at build time.
// On an Android emulator the host machine is 10.0.2.2, not localhost; on a
// real phone use your computer's LAN IP or the deployed API.
export const API_BASE = (process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000').replace(/\/$/, '');

// Base URL for the public recipient page (/v/<slug>). Defaults to the API.
export const SHARE_BASE = (process.env.EXPO_PUBLIC_SHARE_BASE_URL ?? API_BASE).replace(/\/$/, '');

// Standalone credits checkout page (web-checkout/credits.html), hosted outside the app.
export const CHECKOUT_URL = process.env.EXPO_PUBLIC_CHECKOUT_URL ?? '';

// "dev": local demo login (backend needs AUTH_DEV_BYPASS=true). "firebase": real phone OTP.
export const AUTH_MODE = (process.env.EXPO_PUBLIC_AUTH_MODE ?? 'dev') as 'dev' | 'firebase';

// Web client ID from the Firebase / Google Cloud console (OAuth client of type "Web application").
// Needed for "Continue with Google"; the button is hidden while this is empty.
export const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '';

// Phone (SMS) login is built but hidden for now. Set EXPO_PUBLIC_ENABLE_PHONE_LOGIN=true to show it.
export const ENABLE_PHONE_LOGIN = process.env.EXPO_PUBLIC_ENABLE_PHONE_LOGIN === 'true';
