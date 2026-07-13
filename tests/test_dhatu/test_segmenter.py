"""Tests for the local sandhi-aware DP segmenter.

Segmentation tests that hit the DP + kosha require the vidyut data bundle; they
skip when it is absent (CI without ~/.vidyut-data). The rank/pure-helper logic is
tested separately without data.
"""

from __future__ import annotations

import pytest

from sanskrit_analyzer.dhatu import segmenter

pytestmark = pytest.mark.skipif(
    not segmenter.is_available(),
    reason="vidyut sandhi/kosha data bundle not available",
)


def test_segment_empty_returns_empty_list():
    assert segmenter.segment("") == []
    assert segmenter.segment("   ") == []


def test_segment_splits_real_ramayana_compound():
    # इक्ष्वाकुवंशप्रभवो is one fused token that must split into its members.
    members = segmenter.segment("इक्ष्वाकुवंशप्रभवो")
    assert members is not None
    assert "ikṣvāku" in members
    assert "vaṃśa" in members
    assert len(members) >= 3  # ikṣvāku · vaṃśa · prabhava(ḥ)


def test_segment_splits_tapas_compound():
    members = segmenter.segment("तपस्स्वाध्यायनिरतं")
    assert members is not None
    assert "tapas" in members
    assert any(m.startswith("svādhyāya") for m in members)


def test_segment_keeps_single_pada_whole():
    # A word that is itself a valid pada must NOT be force-split.
    members = segmenter.segment("तपस्वी")
    assert members == ["tapasvī"]


def test_segment_full_line_members():
    members = segmenter.segment("इक्ष्वाकुवंशप्रभवो रामो नाम जनैः श्रुतः")
    assert members is not None
    # every member is a non-empty IAST string; the compound is expanded
    assert all(m and isinstance(m, str) for m in members)
    assert len(members) >= 7


def test_segment_slp_short_token_not_split():
    # below the min-split length, returned as-is (no spurious over-segmentation)
    assert segmenter.segment_slp("gam") == ["gam"]
