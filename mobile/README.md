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

Status: typechecks and bundles for Android (`npx expo export --platform android`), but has not been run on a device or emulator. Firebase phone-OTP login is not implemented (needs a Firebase project and a development build). The session token is kept in memory only, so you log in again after restarting the app. Expo's docs were not reachable when this was written, so only core React Native APIs are used.
