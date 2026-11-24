"""Regression tests for honest audio-evidence reporting.

Run: python -m unittest tests.test_acoustic_evidence
"""
import math
import unittest

from acoustic_evidence import inspect_pcm, assess_acoustic_observations


META = {
    "modality": "microphone_pcm",
    "validation_approved": True,
    "model_id": "test-fixture-not-a-real-model",
    "evaluation_set_id": "test-fixture",
}
OBS = {
    "kind": "fathah",
    "start_ms": 100,
    "end_ms": 250,
    "calibrated_probability": .97,
    "acoustic_evidence": "time-aligned acoustic window 100-250ms",
    "expected": "a",
    "observed": "a",
    "outcome": "supported",
    "practice_tip": "Listen and compare with a teacher",
}


class AcousticEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.quality = inspect_pcm([0.1] * 16000, 16000)

    def test_pcm_no_audio(self):
        self.assertFalse(inspect_pcm([], 16000).usable)

    def test_pcm_clipping(self):
        self.assertFalse(inspect_pcm([1.0] * 16000, 16000).usable)

    def test_pcm_silence(self):
        self.assertFalse(inspect_pcm([0.0] * 16000, 16000).usable)

    def test_pcm_nan(self):
        with self.assertRaises(ValueError):
            inspect_pcm([math.nan], 16000)

    def test_no_model_is_uncertain(self):
        out = assess_acoustic_observations(quality=self.quality,
            model_metadata=None, observations=[OBS])
        self.assertEqual(out["status"], "not_verified")
        self.assertEqual(out["findings"][0]["outcome"], "uncertain")

    def test_text_only_cannot_confirm(self):
        meta = dict(META, modality="arabic_asr_text")
        out = assess_acoustic_observations(quality=self.quality,
            model_metadata=meta, observations=[OBS])
        self.assertEqual(out["supported_count"], 0)

    def test_no_acoustic_evidence_cannot_confirm(self):
        item = dict(OBS)
        item["acoustic_evidence"] = ""
        out = assess_acoustic_observations(quality=self.quality,
            model_metadata=META, observations=[item])
        self.assertEqual(out["uncertain_count"], 1)

    def test_uncalibrated_confidence_cannot_confirm(self):
        item = dict(OBS, calibrated_probability=.60)
        out = assess_acoustic_observations(quality=self.quality,
            model_metadata=META, observations=[item])
        self.assertEqual(out["supported_count"], 0)

    def test_bad_timing_cannot_confirm(self):
        item = dict(OBS, end_ms=999999)
        out = assess_acoustic_observations(quality=self.quality,
            model_metadata=META, observations=[item])
        self.assertFalse(out["findings"])

    def test_test_fixture_model_contract(self):
        # Contract behavior only: fixture does not imply real model validation.
        out = assess_acoustic_observations(quality=self.quality,
            model_metadata=META, observations=[OBS])
        self.assertEqual(out["supported_count"], 1)


if __name__ == "__main__":
    unittest.main()
