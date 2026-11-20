# AL-MU'ALLIM 2.0 — ENGINEERING MASTER SPECIFICATION

## Mission
Deliver an exceptionally reliable, accessible, native-feeling Qur'an learning experience on iOS and Android. A global #1 ranking is an aspiration, not a technical acceptance criterion.

## Non-negotiable engineering rules
1. Preserve Quranic integrity: use verified source text, preserve diacritics and verse order, never generate Qur'an text using an LLM.
2. Distinguish audio recognition hypotheses, confirmed word matches, and qualified Tajweed evaluation. Never fabricate phoneme-level certainty.
3. No fake buttons, placeholder playback masquerading as working audio, or success messages before validation.
4. Protect the existing Streamlit main branch. Implement Flutter in flutter_app/ on flutter-foundation-reader until reviewed.
5. All network calls: timeout, retry affordance, pagination, defensive JSON parsing, clear offline state.
6. All user progress: persistent, exportable, privacy-conscious, resilient to interrupted sessions.
7. Avoid audio/3D contention: independent lifecycles, dispose resources, measure frame and recognition latency.
8. Make controls accessible, RTL-aware, screen-reader labelled and usable at large text sizes.
9. No app-store submission until permissions, licensing, content review, privacy policy and platform testing are complete.
10. Every phase requires demonstrable evidence, tests and honest limitation reporting.

## Phase gates

### 1. Flutter foundation and Qur'an reader
- Full 114-surah navigation with names and metadata.
- Correct complete pagination (long surahs cannot silently truncate).
- Reliable API errors, local cache/offline strategy, verified Uthmani text.
- Word study, verse navigation, tap-to-select, manual flag, reveal/hide.
- Reciter audio and word/verse highlighting only when accurate timing exists.
- Accessibility and responsive iPhone, iPad, Android layouts.
**Gate:** widget/unit tests for page merge, duplicate/missing verses, mode and saved flags; test on real devices.

### 2. Live recitation
- Evaluate licensed on-device and streaming Qur'an ASR options.
- Low-latency word alignment and robust handling of fast, repeated or skipped words.
- Separate uncertain recognition from confirmed mismatch; manual correction.
- Measure word error rate, latency, false-positive flags across reciters and environments.
**Gate:** representative audio benchmark and human review; no unverified Tajweed claims.

### 3. Teacher, revision, planner
- Short-phrase rescue, reveal, precise audio loops where licensed timings permit.
- Structured phrase review with manual correct/retry, spaced repetition.
- Teacher guidance grounded in verified Qur'anic references; safe uncertainty handling.
- Editable Hifdh plans and local notifications, with clear permission controls.
**Gate:** persistence, interruption and accessibility tests.

### 4. 3D sanctuary
- Performance-tiered immersive visuals, rain/day-night audio and controls.
- Lazy-load scene, pause when hidden, battery and thermal safeguards.
**Gate:** no measurable degradation of recitation when sanctuary is closed.

### 5. Release readiness
- iOS TestFlight and Android internal/closed testing.
- Legal/licensing review of text, translations, recordings, models and branding.
- Privacy policy, data deletion/export, microphone consent and child-safety review.
- Store assets, device QA, crash monitoring and staged rollout.
**Gate:** independent user tests and app-store policy review.

## Current verified implementation status (2026-11-20)
Flutter foundation contains a basic reader and modes, manually flagged words, and Quran.com API fetch for only the first 50 verses. Listen is a placeholder. Native ASR, teacher, planner, 3D sanctuary and store builds are not implemented. Streamlit has earlier prototypes, not yet ported or certified.

## Work protocol
Inspect source → identify smallest valuable step → implement on development branch → verify diff and compile/tests when tools permit → commit → report exactly what passed and what remains. Never report device tests without a device.
