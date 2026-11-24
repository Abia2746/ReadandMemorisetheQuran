# Seven-part 103-point product upgrade — evidence-gated implementation

## Status as of 24 November 2026

These points are **targets** for an outstanding product, not achieved scores.
Do not claim 103/110, superiority to Tarteel/Tilawa or expert Tajweed accuracy
without comparable independent evaluations.

| Goal | Target | Currently implemented | Remaining evidence/gates |
|---|---:|---|---|
| Validated vowel/consonant recognition | 28 | PCM capture, trainable CTC architecture, hypotheses, refusal when model absent | Rights-cleared trained weights, full Hafs phone inventory, real independent annotated vowel/consonant data, calibration, false-positive and accent audits |
| Teacher-reviewed Tajweed | 23 | Cautious candidate phone aligner, review rubric and evaluation harness | Actual teacher-reviewed findings, true acoustic rule modelling, certified evaluation and disputes |
| Natural interactive Qur'an teacher | 14 | Guided Noor coach with listen/recite/compare/revise, Qari replay, reflections | Low-latency turn-taking, teacher audio dialogue, interruption handling, independently assessed instructional quality |
| Adaptive Hifdh and revision | 15 | Existing Noor plan with Sabq/Sabqi/Manzil, difficult words, editable targets, .ics calendar | Cross-device and missed-day integration/UX testing, notifications where platform permits |
| Premium learner experience | 9 | Existing reader/sanctuary; new accessible four-step practice panel | Usability/device tests, screen reader, performance measurements |
| Production reliability | 9 | API input caps, auth, explicit no-model fallback, CI recipes | Successful builds, device tests, rate limiting, deployment backend, live production health checks |
| Honest evidence and uncertainty | 5 | Reports not certified, uncertainty gates, self-report separated from microphone, consented start | Audit every UI wording and external accuracy claims, independent assessment |

## New learner-facing guided flow

`apps/web/components/audio/GuidedRecitationCoach.tsx` and `apps/web/components/shell/ReadingWorkspace.tsx` show a structured four-step teacher-guided routine.

1. Listen to the original Qari recording, not a generated recitation.
2. Recite using the existing microphone word-following tool (which is not a vowel grader).
3. Compare the sound by listening again.
4. Record a specific uncertainty (fathah/kasrah/dammah, makharij, shaddah, madd, ghunnah, waqf), an optional written reflection and export it.

The reflection is **self-reported** and held in page memory only unless the learner chooses export. Completing four steps does not trigger false 'accurate Tajweed' XP or microphone confirmation. No hidden upload of reflections occurs.

## Release-quality tests to run

```bash
PYTHONPATH=apps/api python -m pytest -q apps/api/tests
python -m unittest tests.test_acoustic_evidence
cd apps/web
npm ci
npm run typecheck
npm run build
```

Then test Safari (iPad/iPhone), Chrome, Android, microphone permission, audio interruption, silent/overdriven input, slow model response, wrong ayah, audio deletion after stopping and changing verses while listening.

## Blocking external dependencies

- No independently validated Qur'anic phoneme weights or expert-labelled evaluation samples have been supplied.
- Some specialised public research models have restricted/non-commercial licences. Confirm rights before shipping in a paid product.
- The Next.js acoustic backend requires separate deployment, secure registry/checkpoint and model runtime resources.
- Current Streamlit deployment is a separate application and does not receive Next.js components automatically.
- Connected Vercel reported a build-rate-limit problem at the last status check; do not infer newer commits reached production.

**Completion definition:** All seven goals pass verifiable acceptance tests, not just checkboxes or generated code.
