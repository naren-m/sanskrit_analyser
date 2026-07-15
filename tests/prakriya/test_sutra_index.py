"""Tests for the sūtra code -> text/gloss index."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.sutra_index import SutraIndex, get_index


def test_lookup_known_sutra():
    idx = SutraIndex.load()
    s = idx.lookup("1.3.1")
    assert s is not None
    assert s.code == "1.3.1"
    assert "BUvAdayo" in s.text


def test_lookup_unknown_code_returns_none():
    idx = SutraIndex.load()
    assert idx.lookup("99.99.99") is None


def test_kashika_stub_tolerated():
    # Bundle kashika.tsv has ~9 rows; 3.2.93 is one of them.
    idx = SutraIndex.load()
    s = idx.lookup("3.2.93")
    assert s is not None and s.kashika  # covered row has gloss
    s2 = idx.lookup("1.3.1")
    assert s2 is not None  # uncovered row: kashika is None, no crash
    assert s2.kashika is None


def test_get_index_cached():
    assert get_index() is get_index()
