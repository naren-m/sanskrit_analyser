"""Tests for script detection and SLP1 normalization.

Regression coverage for the word-initial-capital SLP1 ambiguity: the
ensemble feeds engines already-normalized SLP1, but engines re-detect
the script. Title-case SLP1 like "Bavati" (bhavati) has no interior
uppercase or SLP1-exclusive lowercase, so detect_script falls back to
IAST and a second IAST->SLP1 pass destroys the aspirate ("bavati").
Callers that know their plain-ASCII input is SLP1 pass
plain_ascii_default=Script.SLP1 to resolve the ambiguity.
"""

import pytest

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1


class TestDetectScript:
    def test_devanagari(self):
        assert detect_script("राम") == Script.DEVANAGARI

    def test_iast_with_diacritics(self):
        assert detect_script("rāma") == Script.IAST

    def test_slp1_interior_uppercase(self):
        assert detect_script("rAma") == Script.SLP1

    def test_slp1_exclusive_lowercase(self):
        assert detect_script("gacCati") == Script.SLP1
        assert detect_script("vftti") == Script.SLP1

    def test_plain_ascii_defaults_to_iast(self):
        assert detect_script("bhavati") == Script.IAST

    def test_word_initial_capital_defaults_to_iast(self):
        # Ambiguous: IAST proper noun ("Rama") or SLP1 aspirate ("Bavati").
        # Without a caller hint, plain ASCII stays IAST.
        assert detect_script("Rama") == Script.IAST

    def test_plain_ascii_default_overrides_iast_fallback(self):
        assert detect_script("Bavati", plain_ascii_default=Script.SLP1) == Script.SLP1
        assert detect_script("bhavati", plain_ascii_default=Script.SLP1) == Script.SLP1

    def test_plain_ascii_default_does_not_override_unambiguous(self):
        assert detect_script("राम", plain_ascii_default=Script.SLP1) == Script.DEVANAGARI
        assert detect_script("rāma", plain_ascii_default=Script.SLP1) == Script.IAST
        assert detect_script("rAma", plain_ascii_default=Script.IAST) == Script.SLP1


class TestNormalizeSlp1:
    def test_iast_to_slp1_preserves_aspirate(self):
        assert normalize_slp1("bhavati", Script.IAST) == "Bavati"

    def test_devanagari_to_slp1(self):
        assert normalize_slp1("योगः", Script.DEVANAGARI) == "yogaH"


class TestEngineNormalization:
    """Engines receive SLP1 from the ensemble and must not mangle it."""

    def test_vidyut_normalize_is_idempotent_on_slp1(self):
        from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine

        engine = VidyutEngine.__new__(VidyutEngine)  # skip data-path init
        assert engine._normalize_to_slp1("Bavati") == "Bavati"
        assert engine._normalize_to_slp1("yogaScittavfttiniroDaH") == (
            "yogaScittavfttiniroDaH"
        )

    def test_heritage_normalize_is_idempotent_on_slp1(self):
        from sanskrit_analyzer.engines.heritage_engine import HeritageEngine

        engine = HeritageEngine.__new__(HeritageEngine)
        assert engine._normalize_to_slp1("Bavati") == "Bavati"

    def test_dharmamitra_normalize_treats_plain_ascii_as_slp1(self):
        from sanskrit_analyzer.engines.dharmamitra_engine import DharmamitraEngine

        engine = DharmamitraEngine.__new__(DharmamitraEngine)
        assert engine._normalize_to_iast("Bavati") == "bhavati"

    def test_local_byt5_normalize_treats_plain_ascii_as_slp1(self):
        from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine

        engine = LocalByT5Engine.__new__(LocalByT5Engine)
        assert engine._normalize_to_iast("Bavati") == "bhavati"
