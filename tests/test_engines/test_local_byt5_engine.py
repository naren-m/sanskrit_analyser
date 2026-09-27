"""Tests for the Local ByT5-Sanskrit engine."""

import asyncio
from unittest.mock import patch

import pytest

from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine
from tests._cases import check_cases


def _engine(**kwargs) -> LocalByT5Engine:
    with patch.object(LocalByT5Engine, "_load_model"):
        return LocalByT5Engine(load_on_init=False, **kwargs)


# (id, parser method, raw model output, expected parse)
PARSE_CASES = [
    # Underscore-separated output is the actual model format.
    (
        "segmentation splits on underscores",
        "_parse_segmentation",
        "rāmaḥ_vana_gacchati_",
        ["rāmaḥ", "vana", "gacchati"],
    ),
    (
        "segmentation strips the S task prefix",
        "_parse_segmentation",
        "S rāmaḥ_vana_",
        ["rāmaḥ", "vana"],
    ),
    ("segmentation of empty output is empty", "_parse_segmentation", "", []),
    (
        "lemmatization splits on underscores",
        "_parse_lemmatization",
        "rāma_vana_gam_",
        ["rāma", "vana", "gam"],
    ),
    (
        "lemmatization strips the L task prefix",
        "_parse_lemmatization",
        "L rāma_vana_",
        ["rāma", "vana"],
    ),
    (
        "combined surface_lemma_TAGS tokens, space separated",
        "_parse_combined",
        "rāma_rāma_SNM vanam_vana_SANe gacchati_gam_VP3S",
        [
            {"surface": "rāma", "lemma": "rāma", "tags": "SNM"},
            {"surface": "vanam", "lemma": "vana", "tags": "SANe"},
            {"surface": "gacchati", "lemma": "gam", "tags": "VP3S"},
        ],
    ),
    (
        # For cittavṛttinirodhaḥ the model emits member tokens with an EMPTY
        # surface slot. Naive positional splitting yields surface='' lemma=''
        # tags='citta', losing the lemma into the tags field (observed live,
        # exp5 2026-07). No surface given: fall back to the lemma.
        "compound member __lemma_U keeps its lemma, surface falls back to it",
        "_parse_combined",
        "__citta_U __vṛtti_U nirodhaḥ_nirodha_SNM",
        [
            {"surface": "citta", "lemma": "citta", "tags": "U"},
            {"surface": "vṛtti", "lemma": "vṛtti", "tags": "U"},
            {"surface": "nirodhaḥ", "lemma": "nirodha", "tags": "SNM"},
        ],
    ),
    (
        "empty lemma slot surface__TAG uses surface as lemma",
        "_parse_combined",
        "iti__Cp",
        [{"surface": "iti", "lemma": "iti", "tags": "Cp"}],
    ),
    ("verb tag decodes to verb", "_decode_tags", "VP3S", ("verb", "VP3S")),
    ("noun tag decodes to noun", "_decode_tags", "SNM", ("noun", "SNM")),
    ("empty tags decode to None", "_decode_tags", "", (None, None)),
    ("Devanagari normalizes to IAST", "_normalize_to_iast", "राम", "rāma"),
    (
        # The pipeline hands engines normalized SLP1. 'Bavati' has its only
        # SLP1 marker at position 0, where the interior-capital heuristic can't
        # see it; misdetected as IAST it reached the model unchanged and came
        # back as lemma 'bav' instead of 'bhū' (observed live).
        "word-initial SLP1 capital reaches the model as real IAST",
        "_normalize_to_iast",
        "Bavati",
        "bhavati",
    ),
]


def test_parsers() -> None:
    engine = _engine()

    def check(method, raw, expected):
        got = getattr(engine, method)(raw)
        if method == "_parse_combined":
            got = [{k: item[k] for k in ("surface", "lemma", "tags")} for item in got]
        assert got == expected, f"{method}({raw!r}) = {got!r}"

    check_cases(PARSE_CASES, check)


def test_availability_and_device() -> None:
    engine = _engine()
    assert engine.name == "local_byt5"
    # Not available when the model was never loaded.
    assert not engine.is_available

    auto = _engine(device="auto")
    with patch("torch.cuda.is_available", return_value=False):
        with patch("torch.backends.mps.is_available", return_value=False):
            assert auto._get_device() == "cpu"
    assert _engine(device="cpu")._get_device() == "cpu"


def test_analyze() -> None:
    unavailable = _engine()
    unavailable._init_error = "Model not installed"
    result = asyncio.run(unavailable.analyze("test"))
    assert result.error is not None
    assert "not available" in result.error or "not installed" in result.error
    assert result.confidence == 0.0

    engine = _engine()
    engine._available = True
    result = asyncio.run(engine.analyze(""))
    assert result.segments == []
    assert result.confidence == 0.0

    # Model faked at _generate: combined SLM output, surface_lemma_TAGS.
    engine._generate = lambda text, task: "rāmaḥ_rāma_SNM vanam_vana_SANe gacchati_gam_VP3S"
    result = asyncio.run(engine.analyze("ramo vanam gacchati"))
    assert result.error is None
    assert [(s.surface, s.lemma, s.pos) for s in result.segments] == [
        ("rāmaḥ", "rāma", "noun"),  # SNM = noun
        ("vanam", "vana", "noun"),
        ("gacchati", "gam", "verb"),  # VP3S = verb
    ]


class TestLocalByT5EngineIntegration:
    """Integration tests that require the actual model.

    These tests are skipped if transformers/torch not installed.
    """

    @pytest.fixture
    def skip_if_no_transformers(self) -> None:
        """Skip test if transformers not available."""
        try:
            import torch
            import transformers
        except ImportError:
            pytest.skip("transformers/torch not installed")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_model_loading(self, skip_if_no_transformers: None) -> None:
        """Test loading the real model (slow, requires download)."""
        # This test is slow and downloads ~1GB model
        # Only run explicitly with: pytest -m slow
        pytest.skip("Slow test - run explicitly with pytest -m slow")

    @pytest.mark.asyncio
    async def test_greedy_decode_splits_full_compound(self, skip_if_no_transformers: None) -> None:
        """Greedy decoding must segment the whole compound, not truncate it.

        Regression for the beam-search + early_stopping bug that halted the beam
        at the first EOS and collapsed इक्ष्वाकुवंशप्रभवो to "ik". Runs offline
        against the cached model; skips if the model can't be loaded so CI
        without the weights still passes.
        """
        try:
            engine = LocalByT5Engine()
        except Exception as exc:  # model not cached / load failure
            pytest.skip(f"ByT5 model unavailable: {exc}")

        if not engine.is_available:
            pytest.skip("ByT5 model failed to load")

        verse = "इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः"
        output = engine._generate(engine._normalize_to_iast(verse), "S")
        members = engine._parse_segmentation(output)

        assert len(members) > 1, f"compound not split: {output!r}"
        joined = " ".join(members)
        assert "ikṣvāku" in joined, f"missing ikṣvāku in: {output!r}"
        assert "vaṃśa" in joined, f"missing vaṃśa in: {output!r}"
