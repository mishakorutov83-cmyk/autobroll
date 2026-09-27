#!/usr/bin/env python3
"""Forced-choice check of a doubtful phrase against the ORIGINAL audio (names, apps, numbers).

  ~/.cache/autobroll/dfn-venv/bin/python scripts/reel/verify_phrase.py <ep> <start> <end> "variant 1" "variant 2" ...

Scores each written variant by Whisper large-v3 log-likelihood given the audio of [start, end]
(teacher forcing, no free decoding) and prints them best first. Free ASR on short, quiet phone
speech hallucinates; comparing concrete candidates is far more reliable. Whisper's own language
prior still favours common words, so treat a margin under ~3 as a tie and a nonsensical winner as
"unclear" — cut the words rather than guess. Needs transformers in the dfn venv (~3 GB model).
"""
import subprocess, sys
from pathlib import Path

import numpy as np
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

ROOT = Path(__file__).resolve().parents[2]


def main():
    ep, a, b, cands = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4:]
    src = sorted((ROOT / "work" / ep).glob("source.*"))[0]
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(a), "-to", str(b), "-i", str(src),
                          "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    proc = WhisperProcessor.from_pretrained("openai/whisper-large-v3")
    model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-large-v3").eval()
    feats = proc(x, sampling_rate=16000, return_tensors="pt").input_features
    pre = proc.tokenizer.convert_tokens_to_ids(["<|startoftranscript|>", "<|ru|>", "<|transcribe|>", "<|notimestamps|>"])
    res = []
    with torch.no_grad():
        enc = model.model.encoder(feats).last_hidden_state
        for c in cands:
            ids = pre + proc.tokenizer.encode(" " + c, add_special_tokens=False) + [proc.tokenizer.eos_token_id]
            lg = model(encoder_outputs=(enc,), decoder_input_ids=torch.tensor([ids[:-1]])).logits[0].log_softmax(-1)
            tgt = torch.tensor(ids[1:])
            res.append((float(lg[torch.arange(len(tgt)), tgt][len(pre) - 1:].sum()), c))
    for s, c in sorted(res, reverse=True):
        print(f"{s:8.1f}  {c}")


if __name__ == "__main__":
    main()
