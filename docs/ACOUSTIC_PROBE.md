# Offline acoustic probe for issue #2

The research CLI accepts a local mono 16 kHz PCM16 WAV of 0.25–30 seconds. It evaluates the Muaalem acoustic phoneme head, which has 43 classes including the blank and the three short-vowel marks. It takes no verse text. It collapses the CTC best path into candidate phone symbols. It does not align them to teacher boundaries, score them, or expose an HTTP service. Keep recordings, weights and identifiable results outside this repository.

## Reproduction

In a separate Python 3.12 environment install a CPU build of PyTorch, then install the pinned upstream implementation and feature extractor. The research probe checks all four artifact hashes before inference. Retain the upstream LICENSE and NOTICE. Use a recording permitted for this purpose. The upstream test WAV can be used to reproduce the engineering smoke check.

```sh
git clone https://github.com/obadx/quran-muaalem.git /tmp/muaalem-source
git -C /tmp/muaalem-source checkout b310432c5b6ba272981a67d4cb61438e96349ce7
python -m pip install /tmp/muaalem-source transformers==4.55.4
mkdir -p /tmp/muaalem-model
for file in config.json preprocessor_config.json vocab.json model.safetensors; do
  curl --fail --location "https://huggingface.co/obadx/muaalem-model-v3_2/resolve/01a1ef9fbe40d144ef845101e89ff924aed3fef5/$file" -o "/tmp/muaalem-model/$file" || exit 1
done
HF_HUB_OFFLINE=1 python scripts/probe_muaalem.py /tmp/muaalem-model /tmp/muaalem-source/assets/test.wav /tmp/muaalem-source/NOTICE
```

## Production gate

The [checkpoint card](https://huggingface.co/obadx/muaalem-model-v3_2) tags it MIT. The upstream [QML licence](https://github.com/obadx/quran-muaalem/blob/b310432c5b6ba272981a67d4cb61438e96349ce7/LICENSE) addresses weights, hosted interfaces, advisory notices, advertising and free access. Review the applicable grants and product terms before any customer integration. The production registry accepts a different architecture. Do not register this file there.

No independent learner corpus or expert adjudication was supplied. Before activation, reserve unseen speakers and devices, document consent, record acceptable Hafs variants and obtain independent time-aligned expert audio labels. Freeze model and thresholds before scoring the test split. Report phoneme substitutions, insertions and deletions, each rule's coverage, false corrections, end-to-end recall and reviewer disagreement. For competitor comparison, use identical permitted recordings and product versions, document unsupported tasks and report uncertainty clustered by speaker. A successful forward pass supplies no learner-accuracy estimate.
