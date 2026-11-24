# Separate acoustic phoneme inference service

This is a real pretrained Wav2Vec2-CTC phoneme decoder. It transcribes **observed audio into phone-symbol hypotheses** and estimates model frame timing. It never claims to certify a vowel, Tajweed rule, makhraj or verse completion.

Checkpoint: [FatimahEmadEldin/wav2vec2-xls-r-300m-iqraeval](https://huggingface.co/FatimahEmadEldin/wav2vec2-xls-r-300m-iqraeval), model card Apache-2.0. The model is approximately **1.26 GB** and should run on a separately provisioned CPU/GPU container. Its reported IqraEval F1 is 0.2020; use as **experimental** evidence only, not final correction authority. The model card training data includes Quran and MSA, not comprehensive validated Tajweed for every accent/word.

## Private deployment

Use a dedicated container service such as a trusted GPU host. Keep all audio and secrets private; disable provider request body logging. The model downloads from Hugging Face on first request (cache volume recommended). Never deploy this inside Streamlit Community Cloud, Supabase Edge Functions, or a static Vercel frontend.

Environment:
- `PHONEME_SERVICE_TOKEN`: random strong bearer token of at least 32 characters.
- `PHONEME_MODEL_REVISION`: audited pinned Hugging Face commit (recommended), default main for local exploration.
- Model cache on persistent storage when possible (`HF_HOME`).

```bash
cd phoneme_service
docker build -t almuallim-phonemes .
docker run -p 127.0.0.1:8080:8080 \
  -e PHONEME_SERVICE_TOKEN="<SET_LOCALLY>" \
  -e PHONEME_MODEL_REVISION="<PINNED_REVISION>" \
  almuallim-phonemes
```

Do not place real credentials or users' recordings in a repo. With a private HTTPS reverse proxy in front of the container, send an `audio/wav` request (16-bit PCM, 0.35–15 seconds, max 8 MB) to `POST /v1/phonemes` with `Authorization: Bearer <service token>`.

In **Streamlit secrets** configure:
- `PHONEME_SERVICE_URL`: HTTPS base URL of the private deployed container.
- `PHONEME_SERVICE_TOKEN`: same token stored privately on the service.

Use the separate **Analyse acoustic phonemes (experimental)** button for a given recording. The browser never receives the token. No raw audio is stored in Supabase.

The endpoint can distinguish *proposed short/long vowels* (a/i/u versus aa/ii/uu where present in the vocabulary), consonant identity tokens and possible gemination. It is **not** trained/validated to certify madd or ghunnah durations or all 16 Tajweed topics.

## Verification still required
- [ ] Docker image builds, model weights download with licence reviewed, model pinned and inference runs on real audio.
- [ ] Check model tokenizer vocabulary and CTC blank ID on this exact revision.
- [ ] Run real recitation audio with expected sound/vowel contrasts and log false detections; no artificial pass rates.
- [ ] Qualified Hafs teachers validate held-out recordings across learner levels/microphones/accents.
- [ ] Run a service under HTTPS with network rate limits, per-user quotas, private logs, outbound privacy disclosures and retention controls.
- [ ] Only after independent calibration consider acoustic evidence for teacher-like corrections.

This experimental service does not run in the current public Streamlit deployment until deployed and configured separately.
