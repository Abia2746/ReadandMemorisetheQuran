"""Acoustic engine integration: model must hear audio, never invent correctness."""
from __future__ import annotations
import io
import math
import struct
import unittest
import wave
from unittest.mock import patch

import numpy as np

from phoneme_client import (
    service_ready, sanitize_observation, prepare_acoustic_wav, readable_phone,
    infer_acoustic_phones,
)
from phoneme_service.main import parse_wav, ctc_spans


def pcm_wave(rate=16000, seconds=2):
    buf = io.BytesIO()
    samples = [int(7000 * math.sin(2 * math.pi * 170 * i/rate))
               for i in range(int(rate*seconds))]
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(struct.pack("<" + "h"*len(samples), *samples))
    return buf.getvalue()


class FakeTokenizer:
    def convert_ids_to_tokens(self, index):
        return {1:"b",2:"i",3:"s",4:"mm",5:"aa"}.get(index,"<pad>")


class DecoderTests(unittest.TestCase):
    def test_actual_wav_becomes_mono_16khz_without_new_words(self):
        signal = pcm_wave(rate=8000)
        raw = prepare_acoustic_wav(signal)
        audio, sample_rate = parse_wav(raw)
        self.assertEqual(sample_rate, 16000)
        self.assertAlmostEqual(audio.size/16000, 2.0, places=2)
        self.assertGreater(float(np.max(np.abs(audio))), 0.01)

    def test_silence_and_clipping_fail_closed(self):
        silent = io.BytesIO()
        with wave.open(silent, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00"*16000)
        with self.assertRaises(ValueError):
            parse_wav(silent.getvalue())
        distorted = io.BytesIO()
        with wave.open(distorted, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\xff\x7f"*16000)
        with self.assertRaises(ValueError):
            parse_wav(distorted.getvalue())

    def test_constant_signal_stereo_cancellation_and_partial_wav_are_rejected(self):
        for channels,payload in [(1,struct.pack("<h",4500)*16000),
                                 (2,struct.pack("<hh",4500,-4500)*16000)]:
            buffer=io.BytesIO()
            with wave.open(buffer,"wb") as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(payload)
            with self.assertRaisesRegex(ValueError,"varying audio"):
                parse_wav(buffer.getvalue())
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            parse_wav(pcm_wave()[:-2000])

    def test_ctc_skips_blank_and_repetition(self):
        tokens=ctc_spans([1,1,0,2,2,0,4,4,0,5],
                         [.8,.9,1,.7,.8,1,.85,.86,1,.91],
                         FakeTokenizer(),2.0,0)
        self.assertEqual([x["token"] for x in tokens],["b","i","mm","aa"])
        self.assertTrue(all(x["end_s"] > x["start_s"] for x in tokens))
        self.assertTrue(all(0<=x["model_posterior_mean"]<=1 for x in tokens))

    def test_sound_types_do_not_assert_tajweed_accuracy(self):
        self.assertEqual(readable_phone("a")["kind"],"short_vowel_hypothesis")
        self.assertEqual(readable_phone("ii")["kind"],"long_vowel_hypothesis")
        self.assertEqual(readable_phone("mm")["kind"],"geminated_consonant_hypothesis")
        response={
            "status":"unverified_acoustic_observation",
            "audio_duration_s":2.0,
            "model_id":"some-model",
            "observed_phonemes":[
                {"token":"a","start_s":.2,"end_s":.4},
                {"token":"mm","start_s":.4,"end_s":.7},
            ],
        }
        result=sanitize_observation(response)
        self.assertEqual(result["observations"][0]["status"],"unverified")
        self.assertIn("NOT",result["guidance"]+" NOT")
        self.assertNotIn("correct",result["observations"][0]["kind"])

    def test_special_phone_symbols_in_checkpoint_survive_learner_view(self):
        phones=["*", "**", "$", "$$", "^", "^^", "<", "<<"]
        response={"status":"unverified_acoustic_observation","audio_duration_s":2,
                  "observed_phonemes":[{"token":token,"start_s":i/10,"end_s":(i+1)/10}
                                       for i,token in enumerate(phones)]}
        observed=sanitize_observation(response)["observations"]
        self.assertEqual([item["token"] for item in observed],phones)
        self.assertTrue(all(item["status"]=="unverified" for item in observed))

    def test_claim_outside_clip_or_fake_status_is_rejected(self):
        response={"status":"unverified_acoustic_observation","audio_duration_s":2,
                  "observed_phonemes":[{"token":"i","start_s":3,"end_s":4}]}
        with self.assertRaises(ValueError):
            sanitize_observation(response)
        with self.assertRaises(ValueError):
            sanitize_observation({**response,"status":"certified_correct"})

    def test_url_must_be_private_https(self):
        self.assertFalse(service_ready("http://example.com", "a"*40))
        self.assertFalse(service_ready("https://example.com/?token=foo","a"*40))
        self.assertFalse(service_ready("https://example.com","tiny"))
        self.assertTrue(service_ready("https://example.com","a"*40))

    def test_service_connection_requires_configuration(self):
        with self.assertRaises(RuntimeError):
            infer_acoustic_phones(pcm_wave(), "", "")


if __name__ == "__main__":
    unittest.main()
