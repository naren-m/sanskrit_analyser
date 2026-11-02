"""Tests for the sūtra code -> text/gloss index."""
import json

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


def _write_commentaries(root, kashika, english):
    (root / "sutraani").mkdir(parents=True)
    (root / "sutraani" / "kashika.txt").write_text(json.dumps(kashika))
    (root / "sutraani" / "vasu_english_summary.txt").write_text(json.dumps(english))


# (id, code, want kashika, want english). With no ashtadhyayi.com data the
# Kāśikā is the vidyut bundle's 9-row stub; with it, the repo's 5-digit keys
# ("31091") map onto sūtra codes and Devanagari glosses come back as SLP1.
STUB_CASES = [
    ("stub-covered-row", "3.2.93", "karmaRIti vartamAne", None),
    ("stub-uncovered-row", "1.3.1", None, None),
]
DATA_CASES = [
    ("data-fills-uncovered-row", "1.3.1", "BUvAdayaH SabdAH", "The words bhū etc."),
    ("data-key-with-3-digit-number", "3.1.91", "DAtoH iti", "After a root"),
    ("data-overrides-stub", "3.2.93", "navInA", None),
    # An empty string in the repo means no gloss, not an empty one.
    ("data-empty-entry-dropped", "7.3.84", None, None),
    ("vArttika-codes-untouched", "99.99.99", None, None),
]


def test_commentary_sources_table(tmp_path):
    _write_commentaries(
        tmp_path / "data",
        kashika={"13001": "भूवादयः शब्दाः", "31091": "धातोः इति",
                 "32093": "नवीना", "73084": "  "},
        english={"13001": "The words bhū etc.", "31091": "After a root"},
    )
    failures = []
    for root, cases in ((tmp_path / "absent", STUB_CASES), (tmp_path / "data", DATA_CASES)):
        idx = SutraIndex.load(ashtadhyayi_dir=root)
        for case_id, code, want_kashika, want_english in cases:
            s = idx.lookup(code)
            kashika = s.kashika if s else None
            english = s.english if s else None
            if want_kashika is None:
                kashika_ok = kashika is None
            else:
                kashika_ok = bool(kashika) and kashika.startswith(want_kashika)
            if not (kashika_ok and english == want_english):
                failures.append(f"{case_id}: {code} -> {kashika!r}, {english!r}")
    assert not failures, "\n".join(failures)


def test_get_index_cached():
    assert get_index() is get_index()
