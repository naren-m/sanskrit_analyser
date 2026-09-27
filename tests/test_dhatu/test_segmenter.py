"""Tests for the local sandhi-aware DP segmenter.

Segmentation tests that hit the DP + kosha require the vidyut data bundle; they
skip when it is absent (CI without ~/.vidyut-data).
"""

from __future__ import annotations

import pytest

from sanskrit_analyzer.dhatu import segmenter
from tests._cases import check_cases

pytestmark = pytest.mark.skipif(
    not segmenter.is_available(),
    reason="vidyut sandhi/kosha data bundle not available",
)

# (row id, text, members that must appear, minimum member count)
SPLIT_CASES = [
    # इक्ष्वाकुवंशप्रभवो is one fused token: ikṣvāku · vaṃśa · prabhava(ḥ).
    ("ramayana-compound-splits", "इक्ष्वाकुवंशप्रभवो", {"ikṣvāku", "vaṃśa"}, 3),
    ("tapas-compound-splits", "तपस्स्वाध्यायनिरतं", {"tapas"}, 1),
    # every member of a full line is a non-empty IAST string; compound expanded
    ("full-line-expands-compound", "इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः", set(), 7),
]


def test_segment():
    def check(text, required, min_len):
        members = segmenter.segment(text)
        assert members is not None
        assert all(m and isinstance(m, str) for m in members)
        assert required <= set(members), members
        assert len(members) >= min_len, members

    check_cases(SPLIT_CASES, check)
    assert any(m.startswith("svādhyāya") for m in segmenter.segment("तपस्स्वाध्यायनिरतं"))

    assert segmenter.segment("") == []
    assert segmenter.segment("   ") == []
    # A word that is itself a valid pada must NOT be force-split.
    assert segmenter.segment("तपस्वी") == ["tapasvī"]


def test_segment_slp_short_token_not_split():
    # below the min-split length, returned as-is (no spurious over-segmentation)
    assert segmenter.segment_slp("gam") == ["gam"]
    # non-ASCII (Dravidian short-e sign) panics the splitter; keep it whole
    assert segmenter.segment_slp("kezavaॆrAmo") == ["kezavaॆrAmo"]


# (id, Devanagari line, IAST members that must appear, in order). Each row is a
# real Rāmāyaṇa line the segmenter got wrong, and the row id names the cause.
SUBSEQUENCE_CASES = [
    # Avagraha after a long vowel (not the standard e/o + ऽ) or doubled ऽऽ is
    # outside the splitter's alphabet, so the whole pada came back unsplit.
    # yathāgatam is itself a kosha word ("as come"), so it may stay whole;
    # the point is that the pada splits at all.
    ("avagraha-after-long-a", "यथाऽगतम्", ["yathāgatam"]),
    # Before the fix this whole pada came back as one unsplit token. Where
    # the m of kākutstham lands (kākutstha · muktvā) is a separate tie-break
    # defect: see the note on _solve.
    ("avagraha-in-glued-pada", "काकुत्स्थमुक्त्वाजग्मुर्यथाऽगतम्",
     ["jagmus", "yathāgatam"]),
    ("doubled-avagraha", "सोऽऽहं", ["ahaṃ"]),
    # A visarga written as a sibilant/r at the start of the NEXT pada
    # (स्त्रिय स्स्वर्गे = striyaḥ svarge) belongs to the previous word.
    ("displaced-visarga-ss", "स्त्रिय स्स्वर्गे", ["striyaḥ", "svarge"]),
    ("displaced-visarga-ssh", "यक्षा श्श्रूयन्ते", ["yakṣāḥ", "śrūyante"]),
    ("displaced-visarga-r", "सहस्रदैस्सत्यरतैर्महात्मभि र्महर्षिकल्पै", ["mahātmabhiḥ", "maharṣi"]),
    # A pada with nothing before it keeps its consonant: nothing to move it to.
    ("line-initial-ss-untouched", "स्सर्वे", ["ssarve"]),
    # A stray nukta (पितृ़णां for पितॄणां, 37 verses) survived transliteration
    # as a multi-byte char inside ASCII SLP1 and panicked vidyut's Rust
    # splitter; the panic escaped every handler and hung the request.
    ("nukta-typo-does-not-panic", "पितृ़णां", ["pitṛṇāṃ"]),
    # Standard avagraha already worked and must keep working.
    # A Dravidian short-e (केशवॆ) transliterates to a non-ASCII 'è'; its panic
    # used to drop the whole line rather than leave just that token unsplit.
    ("dravidian-short-e-keeps-line", "केशवॆ रामो गच्छति", ["rāmo", "gacchati"]),
    ("standard-avagraha-e-o", "रामोऽपि", ["rāmas", "api"]),
]


def test_segment_known_failures_table():
    """Rows the reader (#572 follow-up) showed wrong; members must appear in order."""

    def check(line, want):
        got = segmenter.segment(line) or []
        it = iter(got)
        assert all(any(m == w for m in it) for w in want), got

    check_cases(SUBSEQUENCE_CASES, check)
