# Al-Mu'allim · A trustworthy study companion when a Tajweed teacher is unavailable

## Non-negotiable principle
Do not attribute actual endorsement to early Islamic scholars, and do not claim that AI reproduces qualified oral transmission, ijazah, or sanad. The intended standard is *tartil*, care with letters and vowels, humility about uncertainty, and correction by listening to knowledgeable reciters. The software assists daily study and cannot replace a qualified teacher's confirmation when available.

## What users can currently do
1. Pick the exact ayah(s) they actually recited.
2. Record privately and receive an evidence-aware AI review based on the selected Hafs text.
3. Inspect the written vowel, sukun, shaddah and other Uthmani marks for each letter in the reviewed passage.
4. See waveform quality warnings and reject a tentative vowel claim outside an audible region.
5. If the original recorded clip is still present in this browser session, replay a short excerpt near the suggested time (temporary, not cloud-saved).
6. Listen to the selected Hafs reference reciter at the same ayah, and carefully repeat.
7. Mark an AI vowel suggestion as 'practised again' or 'AI may be mistaken'. Such notes are self-reported, not teacher approval.
8. Repeat a guided listen / recite / record / compare cycle without giving a false pass grade.

## Honest accuracy ceiling of the current release
- The live recogniser can confirm ordered **text sequences**, not every phoneme.
- The review prompt can suggest possible Tajweed errors but does not have a validated phoneme-specific acoustic decoder.
- An Uthmani vowel map represents written expectations, not an independent analysis of the learner's vowel.
- A reference reciter's recording is the *whole selected ayah*, not automatically aligned sound-by-sound with the learner clip.
- If the original audio is gone, a cloud-restored review has text notes only; it must never fake an audio replay.
- WAV amplitude/activity detection detects audible sound, not true Arabic vowel identity or a verified word interval.

## Required before calling it a reliable autonomous pronunciation tutor
- Assess real audio using a trained Qur'an phoneme decoder (Hafs 'an 'Asim) and Tajweed-aware phonetic reference.
- Respect valid stopping, connecting and articulation variants; never reject legally valid recitation.
- Support clip time alignment and return a defensible word/letter/phoneme evidence span with uncertainty.
- Include vowels, makharij, shaddah, madd, ghunnah, qalqalah and assimilation where the trained model can demonstrably distinguish them.
- Evaluate against qualified teacher-annotated samples containing genuine learner errors and multiple devices/accents.
- Use the `pronunciation_benchmark.py` metrics. Thresholds in `teacher_review_release_gate` are aspirational engineering gates, not a claim of attained accuracy or scholarly authority.
- Audit incorrect AI corrections as seriously as missed errors. Disclose errors and limitations publicly.

Research bases worth evaluating (none automatically integrated or approved):
- Real-Time Quranic Recitation Assessment on Mobile Devices Using Streaming Inference and Model Compression (ArabicNLP 2026): https://aclanthology.org/2026.arabicnlp-main.30/
- Iqra'Eval 2025 shared task: https://iqraeval-sharedtask-arabicnlp2025.static.hf.space/index.html
- Quran Lab benchmark: https://quranlab.ai/benchmark

**Current production assertion: NOT teacher-level, NOT phoneme-certified, NOT 'better than every Quran app'.**