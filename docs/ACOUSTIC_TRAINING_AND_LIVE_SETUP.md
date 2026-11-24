# Acoustic model training & live app — integration status

Date: 24 November 2026

## Implemented in code

- `scripts/train_quran_phones.py` trains a 201-spectral-bin / BiGRU / CTC acoustic phone network from consented **expert-verified phonetic audio labels**. It refuses train/validation speaker overlap and never auto-approves its own output.
- `apps/api/app/services/acoustic_model.py` accepts real 16 kHz mono PCM16, detects near-silence and clipping, loads an operator-approved SHA256-verified model checkpoint, then decodes phone hypotheses. CTC timing is **approximate** and phone posteriors are **not calibrated pronunciation scores**.
- `apps/api/app/routers/acoustic.py` exposes `GET /api/acoustic/capabilities` and opt-in `POST /api/acoustic/analyse` (octet-stream signed PCM16). Audio is processed in memory only and not intentionally persisted; logging/hosting policy must also be reviewed.
- `apps/web/components/audio/AcousticPractice.tsx` captures opt-in microphone audio through an AudioWorklet and sends short audio windows to the backend. The panel appears in Next.js `ReadingWorkspace`, separate from the existing browser/Whisper text-ASR feedback.
- Tests cover PCM limits, unusable audio and missing-model abstention.

## IMPORTANT: Not finished or deployed

**No real teacher-labelled dataset, trained checkpoint, phoneme-level accuracy measurement, Tajweed validation, or live deployment is provided.** This is a working *trainable architecture and opt-in integration path*, not a fully trained Qur'anic acoustic phoneme recogniser.

The Streamlit deployment is separate from the Next.js app; these changes do **not** update the current Streamlit interface. They do not automatically launch the new web app or train a model.

## Required training data

Create separate JSONL manifests containing only consented, legally licensed, teacher-labelled clips. Each row:

```json
{"audio":"clips/001.wav","speaker_id":"participant-pseudonym-001","phones":["b","a","s","m","i"],"teacher_verified":true}
```

Use a **consistent documented phone inventory for the chosen riwayah**. The sample symbols above are illustrative and do not represent verified Qur'anic pronunciation labels. Include short vowel, consonant and length annotations in a way expert annotators agree upon. Train and validate on separate speakers. Never use original recordings without rights or minors' voices without appropriate consent and safeguarding.

`phones_vocab.json` is a JSON array of distinct acoustic phone tokens, with `"<blank>"` as the first element. Audio: uncompressed mono 16 kHz signed 16-bit PCM WAV, 0.25–8s.

Install `torch` in a separate ML environment (not included in lightweight FastAPI requirements), then:

```bash
PYTHONPATH=apps/api python scripts/train_quran_phones.py \
  --train /secure-data/phones_train.jsonl \
  --validation /secure-data/phones_validation.jsonl \
  --vocabulary /secure-data/phones_vocab.json \
  --output /secure-artifacts/phones_model.pt
```

The model code is intentionally modest; achieving accurate short-vowel identification may require more substantial architecture, high-quality labelled recordings and calibrated phone alignment. Training-set CTC loss alone proves nothing about Tajweed.

## Independent QA and activation

Before use, obtain *independent held-out speaker tests*, teacher review of observed vowels and consonants, false-correction/abstention metrics by feature, noise and iOS/Android device testing, security review, and qualified sign-off.

Only after this, create a **server-only** JSON registry, never in public GitHub:

```json
{
  "approved": true,
  "model_id": "teacher-reviewed-model-version",
  "evaluation_set_id": "heldout-report-version",
  "checkpoint": "/secure-artifacts/phones_model.pt",
  "checkpoint_sha256": "full-sha256-hex",
  "vocabulary": ["<blank>", "example-phone-1", "example-phone-2"]
}
```

Those example vocabulary entries must be replaced with **exactly the training vocabulary in the same order**. Set `ALMUALLIM_ACOUSTIC_REGISTRY=/secure-artifacts/approved-registry.json` in the **backend** environment, install PyTorch and restart FastAPI. Only a trusted operator should create that registry following review. Do not use the approval switch simply to make the UI display results.

Set the Next.js client `NEXT_PUBLIC_API_ORIGIN` to its HTTPS FastAPI backend and explicitly allow the client origin in `CORS_ALLOWED_ORIGINS`. Keep the user informed that audio leaves the device for the chosen backend. Plan authentication/rate limiting and data security before public release.

## Remaining work to satisfy the requested product

The current inference returns **phone hypotheses**, not calibrated rule evaluations. It does not perform word-and-phone-level forced alignment against verified Quran reference text, distinguish rule-specific false corrections reliably, or grade ghunnah, madd, shaddah, makharij, fathah, kasrah or dammah. Train and validate those skills separately, implement teacher-facing dispute review and evidence-linked correction, and integrate the mature recogniser with Streamlit if that remains the primary production client.

No Qur'anic pronunciation result should be presented as verified until independently demonstrated.
