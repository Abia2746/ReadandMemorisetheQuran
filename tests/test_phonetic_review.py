"""Audio vowel evidence: expected Arabic marks must not be mistaken for heard phonemes."""
from __future__ import annotations
import io
import math
import struct
import unittest
import wave

from phonetic_review import (
    phonetic_reference, review_vowel_suggestions, wav_signal_evidence,
)


def wav(samples, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return buf.getvalue()


class PhoneticEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.words = [{"ayah": 1, "ar": "بِسْمِ"},
                      {"ayah": 1, "ar": "اللَّهِ"}]
        self.reference = phonetic_reference(self.words)

    def test_every_harakah_is_mapped_as_written_reference_only(self):
        units = self.reference
        self.assertTrue(any(
            x["letter"] == "ب" and
            any(v["name"] == "kasrah" for v in x["vowels"])
            for x in units))
        self.assertTrue(any(
            x["letter"] == "س" and
            any("sukun" in mark for mark in x["features"])
            for x in units))
        self.assertTrue(any(
            x["letter"] == "ل" and
            any("shaddah" in mark for mark in x["features"])
            for x in units))
        self.assertTrue(all(x["status"] == "not_acoustically_verified"
                            for x in units))

    def test_no_missing_marks_hallucinated(self):
        plain = phonetic_reference([{"ayah": 1, "ar": "كتب"}])
        self.assertEqual(len(plain), 3)
        self.assertTrue(all(not x["vowels"] for x in plain))

    def test_audio_quality_detects_silence(self):
        evidence = wav_signal_evidence(wav([0] * 16000))
        self.assertTrue(evidence["available"])
        self.assertEqual(evidence["quality"], "review_needed")
        self.assertEqual(evidence["duration_s"], 1)
        self.assertLess(evidence["rms"], 0.005)

    def test_audio_quality_detects_clipping(self):
        evidence = wav_signal_evidence(wav([32767] * 16000))
        self.assertEqual(evidence["quality"], "review_needed")
        self.assertGreater(evidence["clipped_fraction"], 0.9)

    def test_clear_signal_is_not_certified_correctness(self):
        samples = [int(8000 * math.sin(2 * math.pi * 180 * n / 16000))
                   for n in range(16000)]
        evidence = wav_signal_evidence(wav(samples))
        self.assertEqual(evidence["quality"], "usable_signal")
        self.assertNotIn("correct", str(evidence).lower())

    def test_tentative_vowel_claim_needs_valid_word_mark_and_timestamp(self):
        good_audio = {"quality": "usable_signal", "duration_s": 5.0}
        candidate = next(x for x in self.reference if x["vowels"])
        row = {
            "word_i": candidate["word_i"],
            "letter_i": candidate["letter_i"],
            "status": "possible_issue",
            "time_s": 2.0,
            "evidence": "There may be an unexpected vowel sound at this point.",
            "guidance": "Listen to the recording beside a qualified reciter.",
        }
        results = review_vowel_suggestions([row], self.reference, good_audio)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "possible_issue_unverified")
        self.assertEqual(review_vowel_suggestions(
            [row], self.reference, {"quality": "review_needed", "duration_s": 5.0}
        ), [])
        self.assertEqual(review_vowel_suggestions(
            [{**row, "time_s": 999}], self.reference, good_audio
        ), [])
        self.assertEqual(review_vowel_suggestions(
            [{**row, "status": "correct"}], self.reference, good_audio
        ), [])

    def test_invalid_audio_never_generates_precision(self):
        result = wav_signal_evidence(b"not a wave recording")
        self.assertFalse(result["available"])
        self.assertEqual(review_vowel_suggestions(
            [{"word_i": 0, "letter_i": 0, "status": "possible_issue",
              "time_s": 0, "evidence": "clearly audible",
              "guidance": "please listen"}], self.reference, result), [])


if __name__ == "__main__":
    unittest.main()
