"""Offline engineering probe for a pinned Muaalem checkpoint and local PCM WAV.

No hub lookups, reference transcript, recording uploads or Tajweed grading.
Setup and model provenance are in docs/ACOUSTIC_PROBE.md.
"""
import argparse
import hashlib
import itertools
import json
import sys
import wave
from pathlib import Path

MODEL_REVISION = "01a1ef9fbe40d144ef845101e89ff924aed3fef5"
HASHES = {
    "model.safetensors": "6b6a2e85303d17ff0f3af5e1fc79ac83daecee409c756ddf27f0ced59393bb41",
    "config.json": "2094c962ca4a167304d8a2c6d2ca429060cbb6c817de09904739ab088bbcf16f",
    "vocab.json": "dcbdac0162632df023002ca1cdd48e74f0f77a328d7f69503f9ff021afb19473",
    "preprocessor_config.json": "8e6281aad64f97e40534135a59dcc5d33571efae376f2a25adf5551951897ab4",
}


def verify(path, digest):
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != digest:
            raise ValueError(f"Unexpected checksum for {path.name}")


def probe(folder, recording):
    import numpy as np
    import torch
    from transformers import SeamlessM4TFeatureExtractor
    from quran_muaalem.modeling.modeling_multi_level_ctc import Wav2Vec2BertForMultilevelCTC

    for name, digest in HASHES.items():
        verify(folder / name, digest)
    with wave.open(str(recording), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, "NONE"):
            raise ValueError("Use mono, 16 kHz PCM16 WAV")
        count = wav.getnframes()
        if not 4000 <= count <= 480000:
            raise ValueError("Expected 0.25 to 30 seconds")
        pcm = wav.readframes(count)
        if len(pcm) != 2 * count:
            raise ValueError("Incomplete recording")
    waveform = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    extractor = SeamlessM4TFeatureExtractor.from_pretrained(folder, local_files_only=True)
    model = Wav2Vec2BertForMultilevelCTC.from_pretrained(
        folder, local_files_only=True, use_safetensors=True
    ).eval()
    vocabulary = json.loads((folder / "vocab.json").read_text())["phonemes"]
    symbols = {index: token for token, index in vocabulary.items()}
    features = extractor(waveform, sampling_rate=16000, return_tensors="pt")
    with torch.inference_mode():
        logits = model(**features, return_dict=False)[0]["phonemes"][0]
        path = logits.argmax(dim=-1).tolist()
    phones = [symbols[i] for i, _ in itertools.groupby(path) if i != vocabulary["[PAD]"]]
    return {"revision": MODEL_REVISION, "duration_seconds": count / 16000,
            "emission_frames": len(path), "phone_hypotheses": phones,
            "tajweed_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("wav", type=Path)
    parser.add_argument("notice", type=Path, help="NOTICE from the pinned upstream source")
    args = parser.parse_args()
    verify(args.notice, "9cb420c5410933cc4d1a35a02a0f8306c860308c6653d761ecd43720470ae4b5")
    print(args.notice.read_text(), file=sys.stderr, flush=True)
    print(json.dumps(probe(args.folder, args.wav), ensure_ascii=False))
