"""Tests for transliteration utilities."""

import pytest

from sanskrit_analyzer.models.scripts import Script, ScriptVariants
from sanskrit_analyzer.utils.transliterate import (
    to_devanagari,
    to_iast,
    to_slp1,
    transliterate,
)
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1


class TestTransliterate:
    """Tests for transliterate function."""

    def test_devanagari_to_iast(self) -> None:
        """Test Devanagari to IAST conversion."""
        result = transliterate("राम", Script.DEVANAGARI, Script.IAST)
        assert result == "rāma"

    def test_devanagari_to_slp1(self) -> None:
        """Test Devanagari to SLP1 conversion."""
        result = transliterate("राम", Script.DEVANAGARI, Script.SLP1)
        assert result == "rAma"

    def test_iast_to_devanagari(self) -> None:
        """Test IAST to Devanagari conversion."""
        result = transliterate("rāma", Script.IAST, Script.DEVANAGARI)
        assert result == "राम"

    def test_iast_to_slp1(self) -> None:
        """Test IAST to SLP1 conversion."""
        result = transliterate("rāma", Script.IAST, Script.SLP1)
        assert result == "rAma"

    def test_slp1_to_devanagari(self) -> None:
        """Test SLP1 to Devanagari conversion."""
        result = transliterate("rAma", Script.SLP1, Script.DEVANAGARI)
        assert result == "राम"

    def test_slp1_to_iast(self) -> None:
        """Test SLP1 to IAST conversion."""
        result = transliterate("rAma", Script.SLP1, Script.IAST)
        assert result == "rāma"

    def test_same_script_returns_input(self) -> None:
        """Test that same source/target script returns input unchanged."""
        text = "राम"
        result = transliterate(text, Script.DEVANAGARI, Script.DEVANAGARI)
        assert result == text

    def test_empty_string(self) -> None:
        """Test that empty string returns empty."""
        result = transliterate("", Script.DEVANAGARI, Script.IAST)
        assert result == ""

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only string returns input."""
        result = transliterate("   ", Script.DEVANAGARI, Script.IAST)
        assert result == "   "

    def test_complex_text(self) -> None:
        """Test transliteration of complex Sanskrit text."""
        # योगश्चित्तवृत्तिनिरोधः (Yoga Sutra 1.2)
        devanagari = "योगश्चित्तवृत्तिनिरोधः"
        iast = transliterate(devanagari, Script.DEVANAGARI, Script.IAST)
        assert "yoga" in iast.lower()
        assert "nirodha" in iast.lower()


class TestConvenienceFunctions:
    """Tests for convenience transliteration functions."""

    def test_to_slp1(self) -> None:
        """Test to_slp1 convenience function."""
        assert to_slp1("राम", Script.DEVANAGARI) == "rAma"
        assert to_slp1("rāma", Script.IAST) == "rAma"

    def test_to_devanagari(self) -> None:
        """Test to_devanagari convenience function."""
        assert to_devanagari("rAma", Script.SLP1) == "राम"
        assert to_devanagari("rāma", Script.IAST) == "राम"

    def test_to_iast(self) -> None:
        """Test to_iast convenience function."""
        assert to_iast("rAma", Script.SLP1) == "rāma"
        assert to_iast("राम", Script.DEVANAGARI) == "rāma"


class TestDetectScript:
    """Tests for script detection."""

    def test_detect_devanagari(self) -> None:
        """Test detection of Devanagari script."""
        assert detect_script("राम") == Script.DEVANAGARI
        assert detect_script("योगश्चित्तवृत्तिनिरोधः") == Script.DEVANAGARI

    def test_detect_iast(self) -> None:
        """Test detection of IAST script."""
        assert detect_script("rāma") == Script.IAST
        assert detect_script("yogaścittavṛttinirodhaḥ") == Script.IAST

    def test_detect_slp1(self) -> None:
        """Test detection of SLP1 script."""
        # SLP1 uses unique markers: w (ṭ), S (ṣ), z (ś), N (ṇ)
        assert detect_script("yogaScittavRttinirodaH") == Script.SLP1
        assert detect_script("rAmazca") == Script.SLP1  # z = ś is SLP1 marker
        assert detect_script("pawati") == Script.SLP1  # w = ṭ is SLP1 marker
        # Note: Plain "rAma" without SLP1 markers defaults to IAST
        # since uppercase alone is ambiguous

    def test_detect_empty_defaults_to_slp1(self) -> None:
        """Test that empty text defaults to SLP1."""
        assert detect_script("") == Script.SLP1
        assert detect_script("   ") == Script.SLP1


class TestNormalizeSlp1:
    """Tests for normalize_slp1 function."""

    def test_normalize_from_devanagari(self) -> None:
        """Test normalization from Devanagari."""
        assert normalize_slp1("राम") == "rAma"

    def test_normalize_from_iast(self) -> None:
        """Test normalization from IAST."""
        assert normalize_slp1("rāma") == "rAma"

    def test_normalize_slp1_unchanged(self) -> None:
        """Test that SLP1 input is returned unchanged."""
        assert normalize_slp1("rAma", Script.SLP1) == "rAma"

    def test_normalize_auto_detect(self) -> None:
        """Test normalization with auto-detection."""
        assert normalize_slp1("राम") == "rAma"  # Auto-detects Devanagari
        assert normalize_slp1("rāma") == "rAma"  # Auto-detects IAST

    def test_normalize_empty(self) -> None:
        """Test that empty string returns empty."""
        assert normalize_slp1("") == ""


class TestScriptVariants:
    """Tests for ScriptVariants dataclass."""

    def test_from_text_devanagari(self) -> None:
        """Test creating ScriptVariants from Devanagari."""
        variants = ScriptVariants.from_text("राम", Script.DEVANAGARI)
        assert variants.devanagari == "राम"
        assert variants.iast == "rāma"
        assert variants.slp1 == "rAma"

    def test_from_text_auto_detect(self) -> None:
        """Test creating ScriptVariants with auto-detection."""
        variants = ScriptVariants.from_text("राम")
        assert variants.devanagari == "राम"
        assert variants.iast == "rāma"
        assert variants.slp1 == "rAma"

    def test_get_script(self) -> None:
        """Test getting text in specific script."""
        variants = ScriptVariants(devanagari="राम", iast="rāma", slp1="rAma")
        assert variants.get(Script.DEVANAGARI) == "राम"
        assert variants.get(Script.IAST) == "rāma"
        assert variants.get(Script.SLP1) == "rAma"

    def test_get_unsupported_script_raises(self) -> None:
        """Test that getting unsupported script raises ValueError."""
        variants = ScriptVariants(devanagari="राम", iast="rāma", slp1="rAma")
        with pytest.raises(ValueError):
            variants.get(Script.HK)

    def test_str_returns_devanagari(self) -> None:
        """Test that str() returns Devanagari."""
        variants = ScriptVariants(devanagari="राम", iast="rāma", slp1="rAma")
        assert str(variants) == "राम"

    def test_frozen(self) -> None:
        """Test that ScriptVariants is immutable."""
        variants = ScriptVariants(devanagari="राम", iast="rāma", slp1="rAma")
        with pytest.raises(AttributeError):
            variants.devanagari = "सीता"  # type: ignore
