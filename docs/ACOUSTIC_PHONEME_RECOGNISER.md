# Trained Qur'anic Acoustic Phoneme Recogniser — Engineering Contract

## Status (24 November 2026)

**Not yet trained, not integrated into the live UI, not deployed.**

The repository now contains `acoustic_evidence.py`, an independent acoustic-evidence reporting and signal-quality contract, and `tests/test_acoustic_evidence.py`. This is *infrastructure* for a future validated model; it cannot hear vowels, makharij, ghunnah or madd by itself. The existing cloud/live and on-device systems remain **word-recognition / word-tracking tools only**. Do not call word matches Tajweed accuracy or infer vowel correctness from fully vowelled Quran text.

## Required recognition stack

1. Capture actual microphone PCM at a known sample rate, with consent and clear local/cloud notice. Use rolling windows and a voice-activity detector; retain audio only with opt-in.
2. Align against the *selected verified riwayah and verse* using independently checked Qur'anic phoneme targets, not a generated guessed transcription. Track word, consonant and vowel positions as distinct units; preserve shaddah as gemination and short vs long vowels.
3. Train or adapt a Qur'anic acoustic phone model with consented labelled human recitation recordings (expert-aligned phone boundaries and rule-appropriate context); report train/validation/test separation by *speaker*, recitation and recording environment. Use actual held-out device and learner accents, not only expert Qari recordings.
4. Include explicit outputs for **fathah /a/, kasrah /i/, dammah /u/**, consonant identity and articulation-related features, shaddah, madd timing, ghunnah and context-dependent Tajweed processes. Some makharij distinctions may be acoustically ambiguous and should remain uncertain rather than labelled wrong.
5. Add CTC/RNN-T or equivalent phone-level decoding and forced alignment; report start/end samples, calibrated per-phoneme posterior distributions, evidence origin and alignment quality. An LLM transcript, even with an Arabic word present, is insufficient.
6. Validate each reported rule against certified Tajweed teachers. Measure false positive rate (especially *false correction*), false negatives, per-rule precision/recall, calibration and abstention, as well as device latency.
7. Produce a session report separating **practised**, **heard with support**, **possible mismatch**, and **uncertain / not evaluated**. Include each reference location, clipped replay segment (opt-in), suggested exercise and user-dispute controls. Never give an overall verified Tajweed score while categories are not validated.

## API evidence boundary

`inspect_pcm(samples, sample_rate)` reports *only* rudimentary audio conditions (duration, RMS, possible clipping, amplitude-based near-silence proxy). It is not voice detection, phoneme recognition or microphone noise removal.

`assess_acoustic_observations(quality=..., model_metadata=..., observations=...)` formats outputs from a **trusted, separately deployed and validated** model. Never accept `validation_approved`, `model_id`, `evaluation_set_id`, probability or evidence strings directly from an untrusted browser. The production server must create these fields from its fixed model registry and verify calibration, model artifact checksums, active supported rule versions, and acoustic inference provenance. A string describing acoustic evidence is a reporting convention, not proof the model actually used audio. Currently no real trusted model registry exists.

Eligible findings must be tied to a time interval, an approved microphone-acoustic model and calibration, and must surpass the confidence gate. Below that gate, classify as **uncertain**, not wrong. Even a 'supported' finding denotes only *support from a validated acoustic model*, not a teacher's certification.

## Acceptance gates

- No speech, one syllable, first letter alone, wrong order, skipped ending, repeated packet and ASR hallucination must never verify an entire word or phrase.
- Short /a/ vs /i/ vs /u/ tests, long-vs-short vowel, shaddah and nasalisation are evaluated independently against expert labels, including deliberate minimal-pair mistakes.
- Noisy and clipped samples produce uncertainty rather than confident feedback.
- Vary speaker, age, accents, device, distance, room, reciter and memorisation speed. Report subgroup performance and prevent disproportionate false corrections.
- Reject out-of-distribution audio and unsupported Qur'anic reading variants.
- Consent, privacy retention limits, age-appropriate notices, audio deletion and data rights must be designed before collecting training recordings.
- Integrate separately into both Streamlit and Next.js only after acoustic inference, tests and device QA. Deploying a source change to the repository does not switch production.

## Baseline checks

```bash
python -m unittest tests.test_acoustic_evidence
node tests/phrase-verification.test.mjs
```

The Python tests verify only the gate's behavior with a **mock model metadata fixture**. They do not validate phonetic accuracy.
