# Phoneme-level Tajweed accuracy programme — Al-Mu'allim

## Current implemented boundary (24 November 2026)
Al-Mu'allim now extracts every explicit vowel/diacritic mark from the selected Uthmani text and displays its expected learning target, recording PCM duration/RMS/peak/clipping quality, and cautious location-specific *hypotheses* where an audio multimodal model provides usable details. It does NOT run a trained Qur'an phoneme or formant detector. A clean waveform means **usable signal only**, not correct pronunciation. Green live phrases represent matching final text only.

## Why a phoneme recogniser is mandatory
Arabic ASR is optimised to recover word text. It may hear the correct Qur'an word despite an incorrect kasrah/fathah, missing shaddah, weak qalqalah or incorrect ghunnah. Without a trained Qur'an phoneme decoder and time-aligned evidence, a real-time 'every vowel right' claim is false.

Relevant research and benchmarks:
- ACL ArabicNLP 2026: Real-Time Quranic Recitation Assessment on Mobile Devices Using Streaming Inference and Model Compression — https://aclanthology.org/2026.arabicnlp-main.30/
- IqraEval QuranMB human-annotated pronunciation benchmark and 68-phoneme inventory — https://iqraeval-sharedtask-arabicnlp2025.static.hf.space/index.html
- Iqra'Eval shared task paper — https://aclanthology.org/2025.arabicnlp-sharedtasks.61/
- Open candidate checkpoint (NOT evaluated by Al-Mu'allim, license/integration not yet confirmed): https://huggingface.co/quran-dev/wav2vec2-ctc-quran-phoneme-run66-iqratts-mix-best-20260909

## Required specialist pipeline (not shipped)
1. Confirm the reading (Hafs 'an 'Asim), source verse, stop/resumption context, Uthmani orthography, and nonlexical pause variation.
2. Create a canonical context-sensitive Qur'an phonemic target, including all short/long vowels, gemination and Tajweed-specific variants; textual marks alone do not represent every spoken phone.
3. Stream 16 kHz PCM through calibrated VAD/noise filter and a trained CTC phoneme + Sifat decoder, storing timestamps and uncertainty for each independently observed phonetic event.
4. Use audio-text forced alignment for time boundaries, but NEVER score against alignment alone: forced alignment can forcibly align wrong speech to an expected word.
5. Detect short-vowel substitutions, missing/conflated consonants, shaddah gemination, madd duration, nasalisation/ghunnah, qalqalah, idgham/ikhfa/iqlab and emphatic quality only with specialised independently validated evidence.
6. Use abstention instead of guessing for first-syllable-only, noisy, clipped, faint, out-of-order, repeated, wrong-ayah or partially recited audio.
7. Verify every student-facing potential error against a time-located audio segment, show the exact expected sound, provide reference slow playback and allow retry/override. Never infer a wrong intention or faith practice from acoustic output.
8. Test and recalibrate on held-out *real human* recitations across learner accents, genders, device microphones, ages, speeds, and recitation styles. Have qualified Hafs teachers independently annotate errors. Audit per-phoneme false alarms, recall and inter-teacher disagreement.

## Objective release gates
- **No misleading green** after a first letter, partial word, interim ASR or position-only event.
- Every model claim must carry a model version, exact audio time range, target phoneme, predicted phoneme, acoustic evidence and confidence calibrated on human labels.
- Fail closed when recogniser is absent, low confidence, silent, clipped or out of scope.
- Report per-vowel substitution precision/recall, false-positive rate, phoneme error rate and timings *on held-out human recordings*; no headline percent from professional reciters alone.
- No production claim that the app is better than every competing Qur'an app without an independently reproducible head-to-head benchmark with identical sample sets and annotation policy.

## Privacy and user experience
Audio analysis needs user permission, clear retention options, and separate controls for saving audio; never publish recitation samples without consent. For minors in particular, avoid public-by-default recordings. User-visible pronunciation findings are unverified practice suggestions until teacher validation.
