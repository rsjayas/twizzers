# Tweezers mobile app (Expo / React Native)

Flow: login -> write or AI-generate a poem -> pick one of 3 variants -> choose style and music -> video renders (the app polls) -> share the link (`/v/<slug>` public page).

```bash
cd mobile
cp .env.example .env     # set EXPO_PUBLIC_API_URL
npm install
npx expo start
npx tsc --noEmit         # typecheck
```

For the full flow run the backend (with `AUTH_DEV_BYPASS=true` while Firebase login isn't wired up, and `RENDER_SERVICE_URL` pointing at `render-service/`) and seed it (`python seed_data.py`).

Layout: `App.tsx` (step state machine), `src/api.ts` (backend client), `src/auth.ts` (auth provider: dev login now, Firebase TODO), `src/screens/*`, `src/ui.tsx` (small shared components).

## Sign-in methods

| Method | State |
|---|---|
| **Email + password** (primary) | Built. Create account, confirm the email, sign in, forgot password, resend the confirmation email. An account must have a confirmed email before it can use the app. |
| **Google** | Built. The button shows when `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` is set. |
| **Phone (SMS code)** | Built but hidden (SMS costs money). Set `EXPO_PUBLIC_ENABLE_PHONE_LOGIN=true` to show it. |

One person is one account: the backend links email + password, Google and phone sign-ins that share a confirmed email (or the same phone number). Firebase project `tweezer-5e9f2`, app ID `com.tweezers.app`; `google-services.json` and `GoogleService-Info.plist` are in this folder (client config, not secrets).

Real login needs a **development build**, not Expo Go (native Firebase and Google modules):

1. In Firebase console > Authentication > Sign-in method: enable **Email/Password** (leave "Email link" off) and, for Google, enable **Google**.
2. In `.env` set `EXPO_PUBLIC_AUTH_MODE=firebase`, `EXPO_PUBLIC_API_URL` to a backend that has `FIREBASE_PROJECT_ID=tweezer-5e9f2` and `AUTH_DEV_BYPASS` off, and for Google `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.
3. Build: `npx eas-cli build --profile development --platform android` (Expo account needed), or locally `npx expo run:android` with the Android SDK.
4. For Google (and phone) on Android, add the build's **SHA-1 and SHA-256** fingerprints in Firebase (Project settings > your Android app; `eas credentials` shows them), then download `google-services.json` again and replace the one here.
5. Optional: customise the verification and password-reset email templates (Firebase console > Authentication > Templates), and restrict the API keys in Google Cloud console to the app's package/bundle ID.
6. Phone only: enable the **Phone** provider, and add fixed test numbers with codes to test without SMS.

With `EXPO_PUBLIC_AUTH_MODE=dev` (default) the app uses a dev login that checks no passwords and still works in Expo Go (`npx expo start --go`).

Status: typechecks and bundles for Android (`npx expo export --platform android`), but has not been run on a device or emulator. Firebase login (email + password, Google, hidden phone) is written but has not been run on a device or against real Firebase; `expo prebuild` succeeds for Android and iOS with the Firebase plugins. In dev mode the session is kept in memory only. Expo's docs were not reachable when this was written, so only core React Native APIs are used.
