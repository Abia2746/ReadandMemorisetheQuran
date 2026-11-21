# Al-Mu'allim migration architecture (2026-11-21)

Status: migration design + starter contracts. The existing Streamlit site stays live while the Next.js and FastAPI applications are built and tested. No production migration is implied by this file.

## Source audit

- Streamlit: app.py, studio_ui.py, tafsir_study_ui.py
- Client study/reader: studio.js, studio.css, hifdh_planner_ui.js, prayer_room_ui.js, prayer_room_lounge_scene.js (Babylon.js).
- Reusable Python: tafsir_sources.py, research_agent.py, timing_data.py, hifdh_planner.py, prayer_room.py, audio_embed.py.
- Separate React/Vite prototype: package.json and src/App.tsx.
- Current progress data: SQLite; not durable on ephemeral Streamlit hosting.
- Existing recognition: experimental @tilawa/core browser engine, browser speech fallback, cloud Gemini live. Do not advertise certifiable Tajweed evaluation.

## Target monorepo

```text
apps/
  web/                              Next.js App Router + React + Tailwind v4
    app/
      layout.tsx
      globals.css
      manifest.ts
      page.tsx                      Read / Memorise landing
      verse/[surah]/[ayah]/page.tsx Verse Studio
      journey/page.tsx              Noor hifdh planner
      sanctuary/page.tsx            Window Lounge
    components/
      shell/StickyReaderBar.tsx
      mushaf/MushafReader.tsx
      mushaf/WordToken.tsx
      mushaf/WordActionPopover.tsx
      audio/RecitationProvider.tsx
      audio/LiveWordAlignment.tsx
      memorise/MeaningTileGrid.tsx
      verse-studio/VerseStudio.tsx
      verse-studio/SourcePills.tsx
      verse-studio/RootFlashcards.tsx
      verse-studio/MasteryDrills.tsx
      journey/NoorPlanner.tsx
      sanctuary/WindowLounge.tsx
    lib/api.ts
    lib/recitation-adapters/{tilawa,gemini,browser}.ts
    public/{icons,fonts,models}/
  api/                              FastAPI + Pydantic v2
    app/
      main.py
      routers/{verse,recitation,planner,progress,rewards}.py
      schemas/verse.py
      prompts/verse.py
      services/{quran,tafsir,drills,morphology,hadith,cache,auth}.py
      repositories/{users,progress,plans}.py
    tests/{test_verse_contracts,test_grounding,test_cache,test_root_words}.py
packages/
  shared/contracts/                 OpenAPI-generated TypeScript types
  shared/design/                    Common color, typography and spacing tokens
legacy/                             Streamlit app during transition, not deleted yet
docs/MIGRATION_ARCHITECTURE.md
```

## Contract and data flow

1. Source of truth: Quran.com Uthmani word data with stable surah/ayah/word index and documented translation edition. Never ask a model to reconstruct the Arabic verse.
2. Verse read: Next Server Component loads canonical verse/translation (cached public data); interactive word actions run in Client Components.
3. GET /api/verse/{surah}/{ayah}/tafsir?lang=en:
   - server retrieves allowlisted tafsir transcriptions (Ibn Kathir, al-Tabari, al-Qurtubi, when present);
   - model drafts structured CLAIMS with source IDs; independent verifier checks valid IDs and quotes, reports uncertainty;
   - return typed blocks and source objects, not Markdown debug tags.
4. GET /api/verse/{surah}/{ayah}/study-drills?lang=en:
   - derive Part A from canonical word list, never an LLM-generated token list;
   - morphological root labels from a curated lexicon with provenance, or mark pending review;
   - derive Part B from actual tafsir corpus and reject overlapping root families and ungrounded entries;
   - generate three independent drill categories with answer keys;
   - fail/return partial when coverage or completion checks fail, never silently truncate.
5. Response caching: (surah, ayah, lang, quran-edition, source-digest, prompt-version, model-version), backed by Redis/managed DB. Do not cache unverified LLM outputs as verified.
6. API returns status complete|partial|unavailable and quality notes separate from presentation. Keep a visible "Sources and verification" disclosure when any claim is uncertain.
7. Generative text is editorial content only. Preserve machine-readable source metadata; handle Arabic markdown/HTML safely without unsanitized rendering.
8. Authentication: per-user OAuth/passkeys or conventional verified login, server-authoritative progress. Use PostgreSQL, not profile names as identities.
9. Recitation engine: one persistent browser client, reused AudioContext, one WebSocket/live adapter at a time; immutable word IDs, explicit pending/confirmed/review states. Red means possible recall/sequence mismatch, not a definitive pronunciation judgement; enable user correction.
10. Planner: carry forward penalty-free sabq/sabqi/manzil logic, difficult-word queue and ICS. Mobile web reminders require supported installed PWA push and explicit permission; .ics is the fallback.
11. Sanctuary: existing Babylon.js scene should be compared against a Three.js port before replacement. Lazy-load renderer, tune quality to devices, cap DPR, pause while off-screen, preserve reduced-motion preferences.

## Step execution order

1. Fix existing Streamlit visual defects and create design system and React header.
2. Migrate reader/audio and isolate recognition adapters; test actual iPad Safari before claiming performance.
3. Implement verse API contracts and four-tab Verse Studio with human-reviewed evaluation fixtures.
4. Meaning tile and voice progress sync.
5. PostgreSQL-backed adaptive planner, calendar export, optional reminders.
6. Three.js (or documented equivalent) sanctuary after profiling existing Babylon scene.

## Acceptance gates

- Core Web Vitals on representative mid-tier iPad/phone; visible Mushaf immediately; no dev banners; readable labels; WCAG contrast checks.
- Word-follower latency measured on real devices, not asserted as zero; no whole-ayah or adjacent-word false confirmation.
- Contract tests reject invented Quranic tokens, ungrounded source IDs, unauthenticated Hadith quotations, and missing drill answer keys.
- No consumer-facing raw [SOURCE n], [NOT VERIFIED], or model log strings. Never silently hide substantive source uncertainty.
- Full regressions for language support, offline fallback, screen reader, low-end GPU and poor network.
- Keep the existing Streamlit app until end-to-end functional parity and data export/migration are verified.
