#!/usr/bin/env python3
"""Train a real (small) acoustic CTC phone recogniser from teacher-labelled WAVs.

This script does NOT ship a dataset or automatically approve a trained model.
Installation (separate ML environment): pip install torch
Usage:
 PYTHONPATH=apps/api python scripts/train_quran_phones.py \
   --train training/phones_train.jsonl --validation training/phones_validation.jsonl \
   --vocabulary training/phones_vocab.json --output training/phones_model.pt

One JSON line: {"audio":"path/to/16k_mono_pcm16.wav",
                "speaker_id":"anonymised-speaker","phones":["b","a","s",...],
                "teacher_verified":true}
IMPORTANT: Phones MUST be expert-aligned acoustic pronunciation labels for
the actual chosen riwayah; never derive labels solely from unvowelled text.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.services.acoustic_model import SAMPLE_RATE, create_network, log_spectrogram


def load_manifest(path: Path, vocabulary: list[str]):
    import torch
    valid_tokens = set(vocabulary[1:])
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip(): continue
            row = json.loads(raw)
            if row.get("teacher_verified") is not True:
                raise ValueError(f"{path}:{line_no}: teacher_verified required")
            speaker = row.get("speaker_id")
            if not speaker or not isinstance(speaker, str):
                raise ValueError(f"{path}:{line_no}: anonymised speaker_id required")
            labels = row.get("phones")
            if (not isinstance(labels, list) or not labels or len(labels)>250
                    or any(phone not in valid_tokens for phone in labels)):
                raise ValueError(f"{path}:{line_no}: bad acoustic label sequence")
            audio = Path(row["audio"])
            if not audio.is_absolute(): audio = path.parent / audio
            with wave.open(str(audio), "rb") as file:
                if (file.getnchannels()!=1 or file.getframerate()!=SAMPLE_RATE
                        or file.getsampwidth()!=2 or file.getcomptype()!="NONE"):
                    raise ValueError(f"{audio}: need mono 16 kHz PCM16 WAV")
                frames = file.readframes(file.getnframes())
            import struct
            nums = struct.unpack("<"+"h"*(len(frames)//2),frames)
            if not .25 <= len(nums)/SAMPLE_RATE <= 8:
                raise ValueError(f"{audio}: expected .25–8 seconds")
            pcm = torch.tensor([x/32768 for x in nums],dtype=torch.float32)
            targets = torch.tensor([vocabulary.index(p) for p in labels],dtype=torch.long)
            rows.append((speaker, pcm, targets))
    if not rows: raise ValueError("Manifest is empty")
    return rows


def run(args):
    import torch
    torch.manual_seed(args.seed)
    if not (args.train.exists() and args.validation.exists() and args.vocabulary.exists()):
        raise ValueError("Expert-labelled data manifests and vocabulary must exist")
    vocab = json.loads(args.vocabulary.read_text(encoding="utf-8"))
    if not isinstance(vocab,list) or not vocab or vocab[0]!="<blank>" or len(set(vocab))!=len(vocab):
        raise ValueError("Vocabulary must be unique, with <blank> at index 0")
    train=load_manifest(args.train,vocab)
    validation=load_manifest(args.validation,vocab)
    train_speakers={r[0] for r in train}
    validation_speakers={r[0] for r in validation}
    if train_speakers & validation_speakers:
        raise ValueError("Training/validation share speakers; held-out validation invalid")
    model=create_network(len(vocab))
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.lr)
    criterion=torch.nn.CTCLoss(blank=0,zero_infinity=True)
    def one_loss(row,train_mode):
        _,audio,labels=row
        features=log_spectrogram(audio).unsqueeze(0)
        logits=model(features)
        if logits.shape[1]<labels.shape[0]*2:
            raise ValueError("Phone targets too long for acoustic frames")
        return criterion(logits.log_softmax(-1).transpose(0,1),
                         labels,torch.tensor([logits.shape[1]]),
                         torch.tensor([labels.shape[0]]))
    best=math.inf
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for epoch in range(args.epochs):
        model.train()
        order=torch.randperm(len(train)).tolist()
        train_loss=0.0
        for i in order:
            optimizer.zero_grad()
            loss=one_loss(train[i],True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
            optimizer.step()
            train_loss+=float(loss.detach())
        model.eval()
        with torch.inference_mode():
            val_loss=sum(float(one_loss(row,False)) for row in validation)/len(validation)
        print(f"epoch {epoch+1}: train_ctc={train_loss/len(train):.4f} validation_ctc={val_loss:.4f}",flush=True)
        if val_loss<best:
            best=val_loss
            torch.save(model.state_dict(),args.output)
    print("Checkpoint created; NOT APPROVED. Requires external held-out phoneme error tests,")
    print("per-harakah validation, false-correction audit, expert review and separate model registry.")
    print("Vocabulary:",json.dumps(vocab,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--train",type=Path,required=True)
    p.add_argument("--validation",type=Path,required=True)
    p.add_argument("--vocabulary",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--epochs",type=int,default=12)
    p.add_argument("--lr",type=float,default=.0003)
    p.add_argument("--seed",type=int,default=47)
    options=p.parse_args()
    if options.epochs<1 or options.epochs>200: p.error("epochs must be 1–200")
    run(options)
