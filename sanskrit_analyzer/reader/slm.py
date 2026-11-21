"""Second proposer: the DCS-trained char-level GPT from naren-m/sanskrit_model.

That model (12.7M params, 4 x 512) was trained by autoresearch on the Digital
Corpus of Sanskrit (Hellwig, CC BY 4.0) for two tasks:

  <dseg> sandhied line            -> padapāṭha (words by space, compound members by "-")
  <dtag> padapāṭha                -> "lemma.CODE" per word, in context

On the held-out DCS dev works it matches ByT5 on segmentation and lemmas and
beats it on run-together text (see sanskrit_model/autoresearch_dcs_longrun_report.md).

Like ByT5, it only *proposes*: every reading still goes through vidyut in
``reader.derive``. The model is configured by two environment variables and is
simply unavailable when they are not set:

  SANSKRIT_SLM_CKPT   path to the checkpoint (e.g. sanskrit_model/data/dcs_v3/ckpt_s30000.pt)
  SANSKRIT_SLM_VOCAB  path to its vocab.json (default: vocab.json next to the checkpoint)

The GPT below is an inference-only copy of sanskrit_model's ``slm.model.GPT``,
because sanskrit_model already depends on this package and cannot be imported
back. Keep the parameter names identical so its state_dict loads unchanged.
"""
from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

from sanskrit_analyzer.reader.tags import Morph

logger = logging.getLogger(__name__)

_CASE = {"1": "praTamA", "2": "dvitIyA", "3": "tftIyA", "4": "caturTI", "5": "paYcamI",
         "6": "zazWI", "7": "saptamI", "8": "samboDanam"}
_GENDER = {"m": "puM", "f": "strI", "n": "napuMsaka"}
_NUMBER = {"s": "eka", "d": "dvi", "p": "bahu"}
_PERSON = {"1": "uttama", "2": "maDyama", "3": "praTama"}
# (tense, mood) -> lakāras. DCS tense "a" (Past) covers perfect, aorist, imperfect.
_LAKARAS = {("r", "I"): ("law",), ("r", "M"): ("low",), ("r", "O"): ("viDiliN", "ASIrliN"),
            ("i", ""): ("laN",), ("a", ""): ("liw", "luN", "laN"), ("f", "I"): ("lfw", "luw"),
            ("", "J"): ("luN", "laN"), ("", "B"): ("ASIrliN",)}
_ALL = ("law", "laN", "liw", "luN", "lfw", "luw", "low", "viDiliN")

_CGN = re.compile(r"([1-8])?([mfn])?([sdp])?")
_VERB = re.compile(r"v([123])([sdp])([riafq])?([IMOJSBCT])?(P)?$")


def code_to_morph(code: str) -> Morph:
    """sanskrit_model's compact DCS tag code -> the reader's Morph."""
    simple = {"c": "compound_member", "u": "avyaya", "a": "absolutive", "t": "avyaya"}
    if code in simple:
        return Morph(simple[code])
    if m := _VERB.match(code):
        tense, mood = m[3] or "", m[4] or ""
        # Injunctive / benedictive mood decides the lakāra whatever the tense says.
        by_mood = _LAKARAS.get(("", mood)) if mood in ("J", "B") else None
        lakaras = (_LAKARAS.get((tense, mood)) or by_mood or _LAKARAS.get((tense, ""))
                   or _LAKARAS.get(("", mood)) or _ALL)
        return Morph("verb", vacana=_NUMBER[m[2]], purusha=_PERSON[m[1]], lakaras=lakaras,
                     prayoga="karmaRi" if m[5] else "kartari")
    if code[:1] in ("n", "k", "g"):
        body = code[1:]
        passive = body.endswith("P")
        body = body.rstrip("P").rstrip("riafq") if code[0] == "k" else body
        m = _CGN.fullmatch(body)
        if m and m[1] and m[3]:
            kind = "nominal" if code[0] == "n" else "participle"
            return Morph(kind, vacana=_NUMBER[m[3]], vibhakti=_CASE[m[1]],
                         linga=_GENDER.get(m[2] or ""),
                         prayoga="karmaRi" if passive else "kartari")
    return Morph("unknown")


def align(padapatha: str, tags: str) -> list:
    """Pair each padapāṭha piece (words and compound members) with its "lemma.CODE"."""
    from sanskrit_analyzer.reader.read import Hypothesis

    pieces = [p for w in padapatha.split() for p in w.split("-") if p]
    tagged = tags.split()
    out = []
    for i, surface in enumerate(pieces):
        lemma, _, code = tagged[i].rpartition(".") if i < len(tagged) else ("", "", "")
        out.append(Hypothesis(surface, lemma or surface, f"slm:{code}", code_to_morph(code)))
    return out


class CharTokenizer:
    """sanskrit_model's SLP1 char tokenizer.

    Control tokens match longest-first, else one id per char.
    """

    def __init__(self, stoi: dict[str, int]):
        self.stoi = stoi
        self.itos = {i: s for s, i in stoi.items()}
        self.pad_id, self.bos_id = stoi["<pad>"], stoi["<bos>"]
        self.eos_id, self.sep_id, self.unk_id = stoi["<eos>"], stoi["<sep>"], stoi["<unk>"]
        controls = sorted((t for t in stoi if len(t) > 1), key=len, reverse=True)
        self._ctrl = re.compile("|".join(re.escape(t) for t in controls)) if controls else None

    @classmethod
    def load(cls, path: Path) -> CharTokenizer:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def encode(self, text: str) -> list[int]:
        ids, i = [], 0
        while i < len(text):
            m = self._ctrl.match(text, i) if self._ctrl else None
            if m:
                ids.append(self.stoi[m.group(0)])
                i = m.end()
            else:
                ids.append(self.stoi.get(text[i], self.unk_id))
                i += 1
        return ids

    def decode(self, ids: list[int]) -> str:
        out = []
        for i in ids:
            if i == self.eos_id:
                break
            tok = self.itos.get(i, "")
            if not (tok.startswith("<") and tok.endswith(">")):
                out.append(tok)
        return "".join(out)


def _build_gpt(cfg: dict):
    import torch.nn as nn
    import torch.nn.functional as F  # noqa: N812 - torch convention: F is torch.nn.functional

    class Attn(nn.Module):
        def __init__(self):
            super().__init__()
            self.n_head, self.n_embd = cfg["n_head"], cfg["n_embd"]
            self.c_attn = nn.Linear(cfg["n_embd"], 3 * cfg["n_embd"], bias=cfg.get("bias", True))
            self.c_proj = nn.Linear(cfg["n_embd"], cfg["n_embd"], bias=cfg.get("bias", True))

        def forward(self, x):
            B, T, C = x.shape  # noqa: N806 - tensor shape names B, T, C
            q, k, v = self.c_attn(x).split(self.n_embd, dim=2)
            h = C // self.n_head
            q, k, v = (t.view(B, T, self.n_head, h).transpose(1, 2) for t in (q, k, v))
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
            return self.c_proj(y.transpose(1, 2).contiguous().view(B, T, C))

    class MLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.c_fc = nn.Linear(cfg["n_embd"], 4 * cfg["n_embd"], bias=cfg.get("bias", True))
            self.c_proj = nn.Linear(4 * cfg["n_embd"], cfg["n_embd"], bias=cfg.get("bias", True))

        def forward(self, x):
            return self.c_proj(F.gelu(self.c_fc(x)))

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.ln_1 = nn.LayerNorm(cfg["n_embd"], bias=cfg.get("bias", True))
            self.attn = Attn()
            self.ln_2 = nn.LayerNorm(cfg["n_embd"], bias=cfg.get("bias", True))
            self.mlp = MLP()

        def forward(self, x):
            x = x + self.attn(self.ln_1(x))
            return x + self.mlp(self.ln_2(x))

    class GPT(nn.Module):
        def __init__(self):
            super().__init__()
            self.block_size = cfg["block_size"]
            self.transformer = nn.ModuleDict(dict(
                wte=nn.Embedding(cfg["vocab_size"], cfg["n_embd"]),
                wpe=nn.Embedding(cfg["block_size"], cfg["n_embd"]),
                h=nn.ModuleList([Block() for _ in range(cfg["n_layer"])]),
                ln_f=nn.LayerNorm(cfg["n_embd"], bias=cfg.get("bias", True)),
            ))
            self.lm_head = nn.Linear(cfg["n_embd"], cfg["vocab_size"], bias=False)
            self.transformer.wte.weight = self.lm_head.weight

        def forward(self, idx):
            import torch
            pos = torch.arange(idx.shape[1], device=idx.device)
            x = self.transformer.wte(idx) + self.transformer.wpe(pos)
            for b in self.transformer.h:
                x = b(x)
            return self.lm_head(self.transformer.ln_f(x))

    return GPT()


class SLMProposer:
    def __init__(self, ckpt: Path, vocab: Path, device: str | None = None):
        import torch

        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        ck = torch.load(ckpt, map_location="cpu", weights_only=True)
        self.model = _build_gpt(ck["cfg"])
        self.model.load_state_dict(ck["model"])
        self.model.to(self.device).eval()
        self.tok = CharTokenizer.load(vocab)

    def _greedy(self, prompt: str) -> str:
        import torch

        ids = [self.tok.bos_id] + self.tok.encode(prompt) + [self.tok.sep_id]
        start, limit = len(ids), min(self.model.block_size, len(ids) + 2 * len(prompt) + 24)
        x = torch.tensor([ids], device=self.device)
        with torch.no_grad():
            while x.shape[1] < limit:
                nxt = self.model(x)[0, -1].argmax().view(1, 1)
                x = torch.cat([x, nxt], dim=1)
                if int(nxt) == self.tok.eos_id:
                    break
        return self.tok.decode(x[0, start:].tolist()).strip()

    def propose(self, text_slp1: str) -> list:
        """Sandhied SLP1 line -> one Hypothesis per padapāṭha piece, tagged in context."""
        padapatha = self._greedy(f"<dseg>{text_slp1.strip()}")
        tags = self._greedy(f"<dtag>{padapatha}") if padapatha else ""
        return align(padapatha, tags)


@lru_cache(maxsize=1)
def get_proposer() -> SLMProposer | None:
    """The configured proposer, or None when SANSKRIT_SLM_CKPT is unset or unloadable."""
    ckpt = os.environ.get("SANSKRIT_SLM_CKPT")
    if not ckpt or not Path(ckpt).is_file():
        return None
    vocab = os.environ.get("SANSKRIT_SLM_VOCAB") or str(Path(ckpt).with_name("vocab.json"))
    try:
        return SLMProposer(Path(ckpt), Path(vocab))
    except Exception as exc:  # missing torch, bad file: the reader falls back to ByT5 / DP
        logger.warning("SLM proposer unavailable: %s", exc)
        return None
