# Al-Mu'allim Next.js PWA / Capacitor client

This folder contains the new standalone **Next.js 16 / React 19 / Tailwind v4**
client for the legacy Streamlit Qur'an learning studio, built as a separate
installable static PWA. The existing Streamlit app remains intact and its
production deployment is **not** automatically switched by these commits.

## What is implemented in source

- Espresso/parchment/gold branded sticky Surah–Ayah–Qari header with a
  free Uthmani Arabic word reader and attributable English translation.
- Client-side Qari playback, source-matched audio range loops, word selection,
  reveal, self-correction and gentle Difficult Words spaced repetition.
- Browser Arabic speech recognition; optional opt-in **on-device Whisper Tiny**
  through a Web Worker/AudioWorklet (first use downloads a model). Neither
  system certifies Tajweed, individual harakah, ghunnah or makharij.
- Memorise with Meaning: English clue tiles, one-letter hints and live
  word recognition reveals, with manuscript-text safety.
- Four-tab Verse Studio: Meaning; Words & Fiqh; Roots & Vocabulary;
  self-graded Arabic Mastery. The two AI endpoints have independent response
  contracts, source provenance and server-side cache.
- A Plan with Noor: PostgreSQL-backed Sabq/Sabqi/Manzil and due difficult words,
  user-editable study days, a gentle no-penalty adaptive target, 90-day ICS.
- Three.js Window Lounge: arched river view, prayer rug, Mushaf stand, benches,
  Qari-study furnishings, named-city visual Fajr/Asr/Isha lighting, optional
  rain animation and generated low-volume rain audio.
- Optional Pro and scholarship interfaces: no ads, no Qur'an paywall.
- Installable manifest, service-worker app-shell fallback, and Capacitor config.

**Not verified yet:** npm/Next build, Python integration tests, hosted API
credentials, Quran Foundation API license/terms, Qari audio distribution rights,
iPad Safari device recognition, Word timing drift, Three.js 60fps, native IAP,
full billing webhook integration and actual App Store / Play Store approval.
An offline app shell is NOT a complete offline Qur'an cache.

## Development

1. Configure the backend first. It is in `apps/api/`. Set
   `DATABASE_URL`, `REDIS_URL`, `OIDC_ISSUER`, `OIDC_AUDIENCE`,
   `OIDC_JWKS_URL`, and **server-only** Quran Foundation
   `QF_CLIENT_ID`, `QF_CLIENT_SECRET`, `QF_CONTENT_SCOPES`,
   plus Gemini model credentials for premium lessons.
   Apply `apps/api/schema.sql` with an approved migration process.
2. In this folder run:

```bash
npm install
cp .env.example .env.local
npm run typecheck
npm run dev
```

3. Set `NEXT_PUBLIC_API_ORIGIN=https://your-api-domain`, an HTTPS
   CORS allowlist in FastAPI, and for study accounts your **public**
   OIDC authority, client ID and API scope (must issue access tokens for
   the backend audience). Do not expose server/client secrets in frontend env.
4. For a static build:

```bash
npm run build
# Next.js emits apps/web/out/
```

5. Install as an HTTPS PWA using the browser's Add to Home Screen /
   Install App option. A verified `manifest.webmanifest`, a suitable
   production app icon and a real service worker are required on the host.
6. To package native iOS/Android, install Xcode/Android Studio, configure
   `@capacitor/ios` and `@capacitor/android`, then sync `out/`. Store
   signing certificates and App Store/Play keys must not enter GitHub.

## Feature configuration, privacy and safety

- **Qur'an content:** the Quran Foundation Content API requires backend-only
  client-credentials OAuth2 with permitted scopes. The Python service renews
  tokens automatically. No Qur'an text is invented when the endpoint fails.
  `https://api-docs.quran.com/docs/quickstart/manual-authentication/`
- **Recitation:** EveryAyah Qari audio sources are matched to QuranLife
  automated word timing tracks. Word highlight follows source timing only
  when all counts and timestamp order check out. Voice word matching is
  not a substitute for a qualified Tajweed teacher.
- **Speech privacy:** browser SpeechRecognition implementations may send
  audio to the browser provider. The optional Whisper worker handles audio
  locally after downloading the model. Inform users before enabling either.
- **Model licensing:** review the exact `onnx-community/whisper-tiny`
  model card, weights and all transitive dependencies before commercial
  distribution. Do not deploy models with non-commercial restrictions.
- **Qur'an licensing:** published translations, recordings and source
  transcriptions have separate rights; do not assume QuranLife CC BY 4.0
  timing licences cover EveryAyah recordings or translation text.
- **Billing:** optional Pro routes require account auth. Basic Qur'an
  reading and Qari audio must remain available even if billing is down.
- **Honesty:** do not advertise objective Tajweed detection, 50ms cold
  cached fetch, zero-delay microphone processing or sustained 60fps until
  device measurements confirm it.

## Engineering acceptance tests still required

- `npm run typecheck && npm run build` on CI; screenshot regression at
  mobile 375px, iPad, landscape tablet and desktop; Lighthouse CWV.
- API schema/contract tests; idempotent free quota and billing checkout
  with simultaneous users; full 6,236 canonical ayahs and Arabic mapping.
- iPhone/iPad Safari microphone permission and local model loading; test
  interruptions, recording stops, mishears, repeated words, hand corrections.
- Load/sync saved plans and Difficult Words on two devices with one account.
- Verify 3D FPS, GPU use, pause/reduced-motion preferences, rain audio mute,
  correct prayertime lighting, material/theme gating, no ads SDKs.
- OIDC callback redirect, GDPR/UK child privacy/consent, production
  subscriptions, RevenueCat transfer and Stripe webhook verification.
