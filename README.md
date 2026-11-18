# Al-Mu'allim · Qur'an learning studio

A responsive original Qur'an learning application built with Streamlit and Streamlit Components v2. Designed for a calm, accessible reading experience on desktop and tablets.

## What is implemented

- **Read** — connected Uthmani Arabic text, verse markers, and word-by-word study. Tap any word to see available transliteration, English meaning, and individual harakah names.
- **Memorise** — English-only clues. Reveal transliteration and vowel names only when requested, either for the passage or an individual word.
- **Listen** — reciter playback for the selected ayahs, with word highlighting only where timestamp data exists.
- **Live word following (beta)** — browser speech recognition follows *approximate* Arabic word positions. A microphone test reports whether audio capture works, separately from recognition. iPad Safari's speech recognition may be unavailable even when microphone access succeeds.
- **Experimental on-device tracking** — opt-in \`@tilawa/core\` / ONNX Runtime WASM engine; the model may not run on all devices. It is not required for Read, Memorise, or Listen.
- **Record and review** — optional Gemini-assisted feedback from recorded audio, using the account owner's configured API key. This is AI practice feedback, not qualified Tajweed certification.
- **Ask the teacher** — questions about vocabulary, verses, and terminology. Responses may be inaccurate and should be verified for religious rulings.
- **Journey** — a local repetition counter plus existing XP and streak tracking.

This application is **not affiliated with Tilawa.ai**. Its visual design, text, and product implementation are original. Live word recognition does **not** reliably assess all 16 Tajweed rules or individual harakah articulation.

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

## Live tracking troubleshooting

1. Select a short passage and press **Test mic**.
2. If the meter moves but live tracking receives no transcript, the browser's speech-recognition service may be unsupported or disabled.
3. Try a supported desktop browser or use the recorded-audio review; **do not interpret silence as a Tajweed mistake**.
4. The experimental on-device option may download a large AI model and is particularly sensitive to iPad Safari / WebAssembly limitations.

## Limitations before production launch

- Validate Arabic recognition against diverse reciters, environments and real user accents.
- Build or integrate a phoneme-alignment and Tajweed model evaluated by qualified Qur'an teachers before presenting letter-level accuracy claims.
- Add authenticated profiles and persistent hosted storage. The current simple SQLite and browser-local progress are not suitable for large multiuser deployment.
- Add user consent, privacy and retention controls for recording-based AI analysis.
- Measure browser compatibility, accessibility, performance and safety under real deployment conditions.

## Automated checks

The GitHub workflow in \`.github/workflows/validate-studio.yml\` validates Python syntax, frontend JavaScript syntax, and presence of the design assets on new commits.
