# Al-Mu'allim · Qur'an learning studio

A responsive original Qur'an learning application built with Streamlit and Streamlit Components v2. Designed for a calm, accessible reading experience on desktop and tablets.

## What is implemented

- **Read** — connected Uthmani Arabic text, verse markers, and word-by-word study. Tap any word to see available transliteration, English meaning, and individual harakah names.
- **Memorise** — English-only clues. Reveal transliteration and vowel names only when requested, either for the passage or an individual word.
- **Listen** — reciter playback for the selected ayahs, with word highlighting only where timestamp data exists.
- **Cloud Live transcription (beta, recommended on iPad)** — after pressing Start, the app requests microphone permission and obtains a short-lived, single-use Gemini token from Streamlit. Your browser streams 16 kHz PCM audio directly to the `gemini-3.5-transcribe-live` model, and returned interim/final Arabic text drives approximate word highlighting. The permanent `GEMINI_API_KEY` stays on the server. This needs an API key with access to the model and may use the account's API quota.
- **Browser word-following fallback** — local browser speech-recognition APIs are offered as an alternative, but Safari may fail even when the microphone itself is working. A separate audio-level test helps distinguish those failures.
- **Qur'an-specific on-device tracking (preview)** — integrates open-source `@tilawa/core@next/web` 1.0 preview API. First use downloads a mobile-oriented acoustic model and Quran reference. Its iOS Safari support is not yet validated. This does not replace a Tajweed teacher.
- **Record and review** — optional Gemini-assisted feedback from recorded audio, using the account owner's configured API key. This is AI practice feedback, not qualified Tajweed certification.
- **Ask the teacher** — questions about vocabulary, verses, and terminology. Responses may be inaccurate and should be verified for religious rulings.
- **Journey** — a local repetition counter plus existing XP and streak tracking.

This application is **not affiliated with Tilawa.ai**. Its visual design, text, and product implementation are original. Live word recognition does **not** reliably assess all 16 Tajweed rules or individual harakah articulation.

## R6: The Prayer Room (19 November 2026)

**New fifth tab: Prayer Room.** A procedural Babylon.js/WebGL sanctuary with curved Islamic architectural arches, a layered mihrab, handcrafted woven rug texture, window-light effects, elegant plaster and walnut materials, warm brass fixtures, orbit/zoom camera controls and optional rainy twilight atmosphere. The 3D library downloads only when opening the room, and rendering pauses when visiting other tabs to reduce iPad battery use. A styled CSS fallback keeps the shop functional if WebGL is unavailable.

**Reward economy (no paywall or real-money purchases):**
- A verse marked **Read** awards **50 permanent XP + 25 spendable coins**.
- A verse marked **Memorised** awards **75 XP + 40 coins**.
- Completing an analysed recitation recording awards **100 XP + 50 coins**, once per unique recording, with a three-reward-per-day cap.
- Each verse/action pair awards XP **once per UTC calendar day** to prevent accidental repeated collection.
- Rewards are **self-reported study progress, not certified Tajweed or verified Hifz accuracy**. Coins are not actual currency.

**Shop:** 14 curated items priced 110–1,200 coins, with separate lifetime-XP unlock requirements. Examples include an olive tree, brass lantern, emerald prayer rug, walnut rehal, carved geometric art, bookshelves, cushions, linen curtains, a golden pendant, rainy window, marble mihrab, travertine floor, midnight-blue rug and candlelit atmosphere. Items can be previewed, purchased, equipped and unequipped. The premium base room is functional before purchasing anything.

**Persistence and limitations:** XP, earned coins, purchases and room equipment are saved transactionally in the existing `muallim.db` SQLite file under the chosen user profile. This preserves state across normal Streamlit reruns and navigation, **but Streamlit Community Cloud local file storage is ephemeral**. Data may reset on app redeployment or instance replacement, and profile names alone are not secure authentication. Migrate the account database to persistent managed storage (e.g., Supabase/Postgres with authentication) before offering reliable multi-device or commercial progression. Browser-local previews are deliberately non-authoritative. Nothing in the Prayer Room changes the Qur'an recognition model.

**Code:** `prayer_room.py`, `prayer_room_scene.js`, `prayer_room_ui.js`, `prayer_room.css`, and tests `tests/test_prayer_room.py` / `tests/prayer-room-ui.test.mjs`.

## R5: following repeated sheikh phrases and short-word sensitivity (19 November 2026)

- **Audio-aware reciter following (beta):** The listening panel now offers *Follow repeated phrases* and *Analyse repeats*. Instead of assuming that a verse's words are spoken only once, the app can analyse the **actual EveryAyah MP3** with the open-source `@tilawa/core` word recogniser. It records `timeMs → {surah, ayah, word}` events, retaining backward movement when the reciter repeats a phrase. The player can then jump backward to the earlier word at the correct audio time.
- **Prepare before listening for repeats:** Press **Analyse repeats** for the current ayah, let the on-device analysis finish, then press Play to use its repeat-aware timeline from the beginning. Automatic analysis also starts during playback, but until it finishes, the player retains ordinary source-matched timestamps.
- **Honest fallbacks:** If the MP3 exceeds size limits, model initialization fails, Safari cannot decode it, or the model detects too few reliable word positions, the existing source-matched timings are used. The recognition engine may miss repetitions or confuse near-identical Quranic passages; this is beta, not guaranteed precision.
- **Low-overhead MP3 preparation:** Python fetches only explicitly known EveryAyah reciter folders, limits each clip to 750 kB and the total selection to 3 MB, and caches clip bytes. In-browser analysis happens locally without uploading the reader's voice. The recognition model is reused for subsequent microphone sessions instead of loading again.
- **Responsive / Careful live word following:** The recitation panel offers a user-selectable confidence threshold. *Responsive* accepts lower-confidence short-word matches, while *Careful* waits for stronger position evidence. It does not provide new vowel, letter or phoneme accuracy. Both modes still mark a word as completed only after the listener advances beyond it; no model can certify a correct word based solely on its initial vowel.
- **Performance:** Browser updates skip redundant full-verse repaint operations, and the live microphone level indicator updates at roughly 14 fps rather than repainting dozens of times per second.

**Testing boundary:** A deterministic mock reproduces a sheikh's pattern of words 1, 2, 3, 1, 2, and verifies that the audio-aware timeline returns the highlight to word 1. This is not a real recitation accuracy test. Real Safari/iPad memory, codec compatibility and on-device recognition need testing with the actual reciter recording.

## R4: reciter synchronisation and recording review (19 November 2026)

- **Yasser Al-Dosari and Mishary Alafasy timing integration:** the app now plays the matching EveryAyah recording for which QuranLife published word timestamps. Automated word timings cover 4,502 Yasser verse records and 6,236 Mishary verse records. Each ayah's word count and timing order are validated before use. Missing or mismatched alignment highlights the **verse only**, not guessed individual words. These word timings are machine-generated and may still drift; no audio timing was human-certified.
- **Source and licence:** derived QuranLife/TimingFilesCode timings are attributed under **CC BY 4.0**, with transformations and full credit in [timings/ATTRIBUTION.md](timings/ATTRIBUTION.md). Using the timings does not transfer ownership of the audio recordings.
- **Recorded review:** a 16-topic Tajweed *study rubric* now explicitly covers articulation, consonant distinctions, short vowels, shaddah, ghunnah, nūn/mīm sākinah rules, qalqalah, madd and waqf. The user chooses which ayah was actually recorded. Each potential AI issue must include a valid word index, audio time, concrete observation and suggested correction; otherwise the finding is labelled *uncertain*. These are **NOT guaranteed acoustic or phoneme-level corrections**, nor a count of 16 universally fixed Tajweed rules.
- **Live memorisation:** the Tilawa SDK follows a locked word position in the selected passage. The word is highlighted as the reciter reaches it, but it is not marked *completed* or revealed in Cover mode until the listener reaches the next consecutive word. Completion indicates approximate passage progress **not Tajweed correctness**. The current SDK does not verify each vowel, ṣād/ḍād distinction, or fine ghunnah/madd articulation.
- **Verified scope:** static JavaScript parsing and mocked frontend scenarios for word timing, fallback verse highlighting, and delayed word reveal. No actual iPad Safari / microphone / model inference test was executed by the assistant. Actual recognition accuracy and generated timestamp alignment need real audio validation before commercial claims.

## Architecture

- \`app.py\` — Quran API retrieval, optional AI review, reciters, session configuration, and progress storage.
- \`studio_ui.py\` — safe Streamlit Components v2 registration and structured data bridge.
- \`studio.js\` — in-page reading, study, memorisation, audio playback, recognition, and microphone diagnostics.
- \`studio.css\` — responsive visual design system.
- \`requirements.txt\` — Python dependencies.

The component is **not sandboxed inside an iframe**. User text arrives via \`component.data\`, and the frontend uses \`textContent\` rather than inserting user-supplied HTML.

## Running locally

1. Install Python 3.11+.
2. Install dependencies with \`pip install -r requirements.txt\`.
3. Run \`streamlit run app.py\`.
4. Use the sidebar to choose a Surah, ayah range, reciter, and tutor.
5. Optional: set \`GEMINI_API_KEY\` in Streamlit secrets or the environment.

Do not commit your API key to GitHub. The app requires HTTPS for browser microphone APIs when deployed remotely.

## Build verification and iPad reliability

The interface shows **Qur'an listener · R3** in the header when the current frontend is loaded. The default recognition method is **Quran-specific model · on-device beta**; the JavaScript bundle is pinned to `@tilawa/core@1.0.0-rc.0/web` and uses the documented `prepareMicrophone`, `createTilawa`, `startMemorization`, `listen`, and locked `position` event interfaces.

The browser module is downloaded from a third-party ESM CDN at startup. The **recognition SDK ready** message means the module loaded, *not* that the model has downloaded or that iPad compatibility is established. Press Start listening to load the model. Successful word-following also requires a supported WebAssembly runtime and microphone capture. SDK/module/runtime failures are reported in the live panel rather than silently substituting Safari's blocked generic speech recognition.

The frontend regression suite (`node tests/studio-ui.test.mjs`) exercises mocked SDK events, iPad-gesture preparation, English-only initial memorisation, correct-word reveal, rejected uncertain positions, and Read-mode highlighting. It **does not** test actual ONNX inference or real iPad hardware. As the upstream SDK notes, iOS Safari has not yet undergone its device-validation programme, so live recitation should remain clearly labelled beta.

## Live tracking troubleshooting

1. Set `GEMINI_API_KEY` in Streamlit Secrets to enable **Cloud Live · recommended**; do not paste the key into the frontend or GitHub.
2. Select a short passage and press **Test mic**.
3. Start **Cloud Live** and allow microphone access. The button requests a single-use token first; watch for the 'microphone streaming' state and the recognised Arabic text.
4. If the meter moves but no transcript appears, the transcription service or network may be unavailable. Do not treat silence as a recitation mistake.
5. The experimental on-device option may download a large AI model and is particularly sensitive to iPad Safari / WebAssembly limitations.

Cloud Live is an optional third-party transcription service. Microphone audio is transmitted to Google only after the user explicitly presses Start. The application does not intentionally persist cloud-streamed audio or its transcript in its own database; Google API data handling and costs depend on the linked plan. Use a separate qualified Tajweed teacher for precise vowel and articulation assessment.

## Limitations before production launch

- Validate Arabic recognition against diverse reciters, environments and real user accents.
- Build or integrate a phoneme-alignment and Tajweed model evaluated by qualified Qur'an teachers before presenting letter-level accuracy claims.
- Add authenticated profiles and persistent hosted storage. The current simple SQLite and browser-local progress are not suitable for large multiuser deployment.
- Add user consent, privacy and retention controls for recording-based AI analysis.
- Measure browser compatibility, accessibility, performance and safety under real deployment conditions.

## Automated checks

The GitHub workflow in \`.github/workflows/validate-studio.yml\` validates Python syntax, frontend JavaScript syntax, and presence of the design assets on new commits.

## Open-source recognition credit

The on-device listener is provided by the **Tilawa** open-source project (`@tilawa/core`, [yazinsai/tilawa](https://github.com/yazinsai/tilawa)). Code is MIT-licensed, while the model/dataset components have separate attribution requirements explained in the upstream [NOTICE.md](https://github.com/yazinsai/tilawa/blob/main/NOTICE.md). The reader and interface in this project remain independently implemented. This project is **not affiliated with or endorsed by Tilawa or Tarteel**. Tarteel does not offer a public recognition API at the time of writing.

Tilawa's 1.0-rc support matrix explicitly lists **iOS Safari as untested**. It checks word errors and skips, not fine articulation or Tajweed; users should not interpret a locked word position as certified pronunciation correctness. Test on real devices before advertising reliable recitation following.
