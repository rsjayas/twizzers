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

## Real login (Firebase phone OTP)

Firebase project `tweezer-5e9f2`, app ID `com.tweezers.app`; `google-services.json` and `GoogleService-Info.plist` are in this folder (client config, not secrets).

Phone login needs a **development build**, not Expo Go (native Firebase module):

1. In `.env` set `EXPO_PUBLIC_AUTH_MODE=firebase` and `EXPO_PUBLIC_API_URL` to a backend that has `FIREBASE_PROJECT_ID=tweezer-5e9f2` (and `AUTH_DEV_BYPASS=false` or unset).
2. Build: `npx eas-cli build --profile development --platform android` (Expo account needed), or locally `npx expo run:android` with the Android SDK installed.
3. In the Firebase console add the build's **SHA-1 and SHA-256** fingerprints (Project settings > your Android app). `eas credentials` shows them for EAS builds. Without these, Android phone verification fails.
4. In Firebase console > Authentication enable the **Phone** provider. For testing without SMS, add test phone numbers with fixed codes there.
5. Optional: restrict the API keys in Google Cloud console (Credentials) to the app's package/bundle ID.

With `EXPO_PUBLIC_AUTH_MODE=dev` (default) the app uses the dev login and still works in Expo Go (`npx expo start --go`).

Status: typechecks and bundles for Android (`npx expo export --platform android`), but has not been run on a device or emulator. Firebase phone-OTP login is written (send code, verify, restore session, token refresh) but has not been run on a device or against real Firebase; `expo prebuild` succeeds for Android and iOS with the Firebase plugins. In dev mode the session is kept in memory only. Expo's docs were not reachable when this was written, so only core React Native APIs are used.
