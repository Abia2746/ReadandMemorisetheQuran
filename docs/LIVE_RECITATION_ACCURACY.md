# Live recitation: completion-proof alignment

## Bug fixed (24 November 2026)
Previously the main reader could paint words as completed after a few on-device 'locked' position events, which could occur while the learner was still pronouncing the first sound. Browser/cloud streams could also advance word by word before the complete phrase was recognised.

## New visible behavior
- **Purple / tentative** — the on-device Qur'an tracker estimates the current word or location. No verified XP/progress, no Arabic reveal in blind memorisation, even after repeated locked observations.
- **Green / confirmed text phrase** — only a FINAL Arabic transcription with every expected word in the current contiguous phrase, exactly and in order, advances through the phrase. Phrases have up to four words and do not cross ayah boundaries. The final ayah phrase can be shorter.
- **Unverified / incomplete** — a single letter, the first full word, a missing or reordered word, approximate match, or interim transcript does not complete the phrase.
- Cloud final text chunks are accumulated and overlapping repeated transcript prefixes are deduplicated; an incomplete phrase stays unconfirmed.
- The live recognition selector now prefers Cloud Live when configured; otherwise uses browser transcription when offered, and local Qur'an position estimation as a fallback.
- The progress bar for the local SDK is based on confirmed progress, not its guessed current position.

## Scope and honesty
Arabic ASR matching compares transcribed word spelling only after removing diacritics; it **cannot verify individual vowels, elongation, makharij, ghunnah, or the complete 16 Tajweed rules**. Even a 'confirmed phrase' means the textual sequence was recognised, NOT that every phoneme was correct. A language-model recogniser may hallucinate familiar Qur'anic text; audio-level alignment and independent acoustic evidence remain necessary to distinguish that.

### What 'maximum potential' needs next
1. Streaming Qur'an-constrained acoustic/phonetic decoder and forced alignment to exact reference segment, with word-boundary timing confidence.
2. A separate letter and harakah scoring model evaluated on real recitations and multiple reciters/accents, with human Tajweed teacher validation. Do not mark an entire phrase correct on transcript similarity alone.
3. Per-phoneme uncertainty: distinguish 'not heard clearly' from a likely omission or substitution, and do not create red errors on noisy audio.
4. Real-time microphone calibration and voice-activity detection; detect wrong verse, repeated words, skips, insertions and partial completion without rewarding guesses.
5. Explicit review for questionable phrases with playback of the selected phrase, slow repetition, and learner dispute/override controls.
6. Validation on iPad Safari, Chrome and Android, including near-silent input, first-phoneme-only, incomplete 3-of-4 words, missing final consonant, and repeated transcription packets.

Regression tests: `node tests/phrase-verification.test.mjs` and `node tests/studio-ui.test.mjs`. The former directly checks that missing words, changed order, a first letter and partial phrases cannot become confirmed. Tests are included in GitHub CI; passing CI and live device tests must still be verified.

**No claim is made that AI output is a qualified Tajweed certification.**