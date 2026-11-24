# Acoustic recogniser readiness report — 24 November 2026

## Current assessed status

**Training weights: NOT DELIVERED.** No rights-cleared, expert-annotated recording corpus and no independently evaluated phoneme model checkpoint are available to this repository. The CTC network and training script in `scripts/train_quran_phones.py` are executable only once these inputs are provided. Claiming a trained model without fitting real data would be false.

**Fathah, kasrah and dammah accuracy: NOT VALIDATED.** Distinct model-phone targets and per-vowel held-out examples are required. No genuine measured confusion matrix exists.

**Shaddah, madd, ghunnah, makharij: NOT VALIDATED.** The newly added alignment tests include artificial phone examples illustrating substitutions or omissions but these test software behavior, *not recognition accuracy*. Duration and nasalisation need specially reviewed acoustic annotations.

**Reference alignment: CANDIDATE IMPLEMENTATION COMMITTED.**
- `apps/api/app/services/phoneme_alignment.py`: deterministic edit alignment with insertion, deletion and substitution candidates.
- `apps/api/app/routers/acoustic.py`: optional `X-Quran-Verse` selects a **server-registry** reviewed phone sequence; client is never permitted to declare arbitrary Qur'anic phone references authoritative.
- `apps/web/components/audio/AcousticPractice.tsx`: displays possible differences marked uncertain.
- If reference is not present, report `reference_unavailable`. Never create reference labels by guessing.

**Accuracy harness: COMMITTED, NOT POPULATED WITH REAL EVALUATION DATA.**
- `apps/api/app/services/phoneme_evaluation.py`: phone edit metrics and teacher-error precision, recall and false-correction rate for each feature.
- `apps/api/tests/test_phoneme_alignment.py`: software correctness tests, **not model validation**.
- An authenticated user session is required for raw-mic inference. Review rate limits and server quotas before public API deployment.

## Public research and licensing candidates to evaluate

1. Quran-Lab Zipformer phoneme recogniser: https://huggingface.co/Quran-Lab/zipformer_p-arabic-v3 . It is published with a Quran-Lab **No-Profit License**. Do not use for paid Al-Mu'allim without compliant rights or separately negotiated permission.
2. Quran-Lab MFA Quran Hafs aligner: https://huggingface.co/Quran-Lab/mfa-quran-hafs . Read the exact model and dictionary terms before use.
3. quran-dev wav2vec2 CTC phoneme model: https://huggingface.co/quran-dev/wav2vec2-ctc-quran-phoneme-run66-iqratts-mix-best-20260909 . Inspect exact model card/license and provenance before any download or integration.
4. Research phonetic datasets: https://huggingface.co/datasets/Quran-Lab/quran-tajweed-phonetics and https://huggingface.co/datasets/hetchyy/everyayah-phonemes . Automatically generated reference phone labels are **not substitutes for teacher-labelled real pronunciation mistakes**, especially for false-correction testing.
5. API service option: https://nabrquran.ai/en . Commercial terms, data handling and reported accuracy require separate due diligence before integration.

## Deployment blocker

The connected Vercel project `al-muallim-safari-preview` had a READY deployment for historical commit `a65062261a36ed6fa90c243b3732ef86105f97c4`. More recent commits report `Vercel: failure` with an `upgradeToPro=build-rate-limit` link. This is not a deployed verified acoustic model. Do not present old READY previews as the latest acoustic release.

The **Streamlit application remains a separate production frontend** and has not been updated by these Next.js changes.

## Release gates that must remain closed

- Obtain rights-cleared audio, verified Qur'anic phone targets and real teacher-labelled errors for the chosen Hafs reading.
- Train or license suitable real pretrained weights; evaluate against independent held-out speakers and devices.
- Publish numerical *per-class* metrics, calibration and false-correction rate; define validated abstention thresholds and teacher review.
- Approve a model registry with SHA256 of evaluated weights and canonical phone references, stored privately on the backend.
- Run `PYTHONPATH=apps/api pytest apps/api/tests` and `cd apps/web && npm run typecheck && npm run build`.
- Review runtime resource limits, audio privacy policies, authenticated API rate limits, QA on Safari/Android, and verify a successful fresh deployment before production cutover.

Until then the feature MUST remain visibly experimental and fail closed.
