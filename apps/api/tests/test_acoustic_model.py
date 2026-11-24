"""No pretrained audio weights required: prove signal checks and honest fallback."""
import struct
import pytest

from app.services.acoustic_model import decode_pcm16, audio_quality, collapse_ctc_frames


def pcm(value: int, frames: int = 16000):
    return struct.pack("<" + "h" * frames, *([value] * frames))


def test_silence_refused():
    quality = audio_quality(decode_pcm16(pcm(0)))
    assert quality["usable"] is False
    assert "quiet_audio" in quality["reasons"]


def test_clipped_audio_refused():
    quality = audio_quality(decode_pcm16(pcm(32767)))
    assert quality["usable"] is False
    assert "clipping" in quality["reasons"]


def test_moderate_audio_is_usable_not_proof_of_pronunciation():
    quality = audio_quality(decode_pcm16(pcm(4000)))
    assert quality["usable"] is True
    assert "tajweed_verified" not in quality


@pytest.mark.parametrize("payload", [
    b"", b"odd", pcm(300, 1000), pcm(300, 16000 * 9),
])
def test_invalid_duration_or_pcm(payload):
    with pytest.raises(ValueError):
        decode_pcm16(payload)


def test_no_registry_never_fakes_model(monkeypatch):
    monkeypatch.delenv("ALMUALLIM_ACOUSTIC_REGISTRY", raising=False)
    from app.services.acoustic_model import load_approved_model
    load_approved_model.cache_clear()
    with pytest.raises((RuntimeError, ImportError)):
        load_approved_model()


def test_ctc_contiguous_frames_have_real_intervals():
    vocab = ["<blank>", "a", "i"]
    # Two separate a sounds with a blank separator, then a different vowel.
    result = collapse_ctc_frames(
        [0, 1, 1, 1, 0, 1, 1, 0, 2, 2, 0], vocab, 110
    )
    assert [item["phone"] for item in result] == ["a", "a", "i"]
    assert all(0 <= item["approx_start_ms"] < item["approx_end_ms"] <= 110
               for item in result)
    assert result[0]["approx_end_ms"] > result[0]["approx_start_ms"] + 20


def test_ctc_all_blank_does_not_invent_a_sound():
    assert collapse_ctc_frames([0, 0, 0, 0], ["<blank>", "a"], 40) == []


def test_ctc_out_of_vocab_is_rejected():
    with pytest.raises(ValueError):
        collapse_ctc_frames([1, 2], ["<blank>", "a"], 40)
