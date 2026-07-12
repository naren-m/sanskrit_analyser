"""Tests for script detection in sanskrit_analyzer.utils.normalize."""

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script


class TestDetectScript:
    def test_devanagari(self) -> None:
        assert detect_script("राम") == Script.DEVANAGARI

    def test_iast_diacritics(self) -> None:
        assert detect_script("rāma") == Script.IAST

    def test_slp1_interior_capital(self) -> None:
        assert detect_script("rAma") == Script.SLP1

    def test_plain_ascii_defaults_to_iast(self) -> None:
        """IAST proper nouns with title-case must not be misread as SLP1."""
        assert detect_script("Rama") == Script.IAST

    def test_plain_ascii_default_override_slp1(self) -> None:
        """Pipeline callers know their text is SLP1 and can say so.

        Word-INITIAL SLP1 capitals (Bavati = bhavati, DarmaH = dharmaḥ) carry
        no interior-capital signal, so the detector cannot distinguish them
        from IAST title-case. Callers that receive pipeline-normalized SLP1
        pass plain_ascii_default=Script.SLP1 to resolve the ambiguity.
        """
        assert detect_script("Bavati", plain_ascii_default=Script.SLP1) == Script.SLP1
        # Unambiguous scripts are unaffected by the default
        assert detect_script("rāma", plain_ascii_default=Script.SLP1) == Script.IAST
        assert detect_script("राम", plain_ascii_default=Script.SLP1) == Script.DEVANAGARI
        assert detect_script("rAma", plain_ascii_default=Script.SLP1) == Script.SLP1
