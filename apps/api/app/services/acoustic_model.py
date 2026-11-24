"""Optional trained acoustic phone model. Never substitute ASR for phoneme evidence.

Model weights are loaded only from a server-owned approved checkpoint.
This is infrastructure; no weights or expert validation dataset are shipped.
"""
from __future__ import annotations
import json
import math
import os
import struct
import wave
from functools import lru_cache
from pathlib import Path

SAMPLE_RATE = 16000
MIN_SECONDS = 0.25
MAX_SECONDS = 8.0


def decode_pcm16(data: bytes) -> list[float]:
    if not data or len(data) % 2 or len(data) > SAMPLE_RATE * 2 * MAX_SECONDS:
        raise ValueError("Expect 0.25–8 seconds of mono 16 kHz signed PCM16")
    samples = struct.unpack("<" + "h" * (len(data) // 2), data)
    if not MIN_SECONDS <= len(samples) / SAMPLE_RATE <= MAX_SECONDS:
        raise ValueError("Audio duration is outside the permitted range")
    return [x / 32768.0 for x in samples]


def audio_quality(samples: list[float]) -> dict:
    n = len(samples)
    rms = math.sqrt(sum(x * x for x in samples) / n)
    peak = max(abs(x) for x in samples)
    clipped = sum(abs(x) >= .998 for x in samples) / n
    reasons = []
    if rms < .008: reasons.append("quiet_audio")
    if clipped > .01: reasons.append("clipping")
    return {"usable": not reasons, "rms": round(rms, 4),
            "clipped_fraction": round(clipped, 4), "reasons": reasons}


def log_spectrogram(waveform):
    """26? No: 201-bin 25ms / 10ms log STFT from 16k mono audio."""
    import torch
    window = torch.hann_window(400, device=waveform.device)
    spec = torch.stft(waveform, n_fft=400, hop_length=160,
                      win_length=400, window=window,
                      return_complex=True).abs()
    return torch.log1p(spec.transpose(-2, -1))


def create_network(n_tokens: int):
    import torch.nn as nn
    class PhoneCTC(nn.Module):
        def __init__(self):
            super().__init__()
            self.pre = nn.Sequential(nn.LayerNorm(201), nn.Linear(201, 192), nn.GELU())
            self.rnn = nn.GRU(192, 160, num_layers=2, batch_first=True,
                              bidirectional=True, dropout=.12)
            self.head = nn.Linear(320, n_tokens)
        def forward(self, features):
            x, _ = self.rnn(self.pre(features))
            return self.head(x)
    return PhoneCTC()


@lru_cache(maxsize=1)
def load_approved_model():
    """Refuse model output until deployment operator approves audited weights.

    Approval requires a manually supplied deployment registry JSON outside git,
    not a training-script self-assertion.
    """
    import torch
    registry_path = os.getenv("ALMUALLIM_ACOUSTIC_REGISTRY", "")
    if not registry_path:
        raise RuntimeError("No expert-validated Qur'anic acoustic model is configured")
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    if (registry.get("approved") is not True
            or not registry.get("evaluation_set_id")
            or not registry.get("model_id")
            or not registry.get("checkpoint_sha256")
            or not registry.get("vocabulary")):
        raise RuntimeError("Acoustic model registry has not passed approval")
    path = Path(registry["checkpoint"])
    import hashlib
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != registry["checkpoint_sha256"]:
        raise RuntimeError("Acoustic model checksum differs from approved artifact")
    vocabulary = registry["vocabulary"]
    if not isinstance(vocabulary, list) or len(set(vocabulary)) != len(vocabulary):
        raise RuntimeError("Invalid model vocabulary")
    if not vocabulary or vocabulary[0] != "<blank>":
        raise RuntimeError("CTC blank must be vocabulary index 0")
    model = create_network(len(vocabulary))
    state = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model, registry


def analyse(samples: list[float]) -> dict:
    """Actual microphone signal -> trained CTC acoustic phone hypotheses.

    CTC softmax is **not** calibrated correctness probability. No Tajweed
    verdicts, vowel accuracy or teacher certification are produced here.
    """
    import torch
    model, registry = load_approved_model()
    with torch.inference_mode():
        signal = torch.tensor(samples, dtype=torch.float32)
        emissions = model(log_spectrogram(signal)).softmax(-1)
        indices = emissions.argmax(-1).tolist()
        phones = []
        previous = 0
        for frame, index in enumerate(indices):
            if index != 0 and index != previous:
                phones.append({
                    "phone": registry["vocabulary"][index],
                    "approx_start_ms": max(0, frame * 10 - 12),
                    "approx_end_ms": (frame + 1) * 10 + 12,
                    "uncertainty": "Uncalibrated phone hypothesis; teacher validation required",
                })
            previous = index
    return {
        "status": "acoustic_hypotheses_only",
        "model_id": registry["model_id"],
        "evaluation_set_id": registry["evaluation_set_id"],
        "phones": phones[:250],
        "tajweed_verified": False,
        "message": "Acoustic phone hypotheses only; phoneme accuracy and Tajweed are not certified.",
    }
