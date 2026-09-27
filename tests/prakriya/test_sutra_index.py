"""Tests for the sūtra code -> text/gloss index."""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.sutra_index import SutraIndex, get_index
from tests._cases import check_cases

# (id, code, substring of the sūtra text or None when unknown, has kashika gloss)
LOOKUP_CASES = [
    ("known-sutra-1.3.1-text", "1.3.1", "BUvAdayo", False),
    ("unknown-code-is-none", "99.99.99", None, False),
    # Bundle kashika.tsv has ~9 rows; 3.2.93 is one of them. 1.3.1 is not, so
    # its kashika is None with no crash (row above).
    ("kashika-stub-covered-row-has-gloss", "3.2.93", "", True),
]


def test_lookup():
    idx = SutraIndex.load()

    def check(code, text, has_kashika):
        s = idx.lookup(code)
        if text is None:
            assert s is None
            return
        assert s is not None
        assert s.code == code
        assert text in s.text
        assert bool(s.kashika) is has_kashika
        if not has_kashika:
            assert s.kashika is None

    check_cases(LOOKUP_CASES, check)


def test_get_index_cached():
    assert get_index() is get_index()
