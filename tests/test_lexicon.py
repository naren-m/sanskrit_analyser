"""Layer B lexicon lookup across the five bundled CDSL tables."""

from __future__ import annotations

import pytest

from sanskrit_analyzer import lexicon

pytestmark = pytest.mark.skipif(
    not lexicon.is_available(), reason="Layer B TSVs not present"
)


def test_all_five_sources_present():
    assert lexicon.available_sources() == [
        "abhidhanacintamani",
        "abhidhanaratnamala",
        "krdanta",
        "skd",
        "vcp",
    ]


# "rāma" is spelt differently in all three encodings, unlike "yoga" whose IAST
# and SLP1 forms are the same string.
@pytest.mark.parametrize("word", ["राम", "rāma", "rAma"])
def test_lookup_accepts_any_script(word):
    """Devanāgarī, IAST and SLP1 all normalise to the same SLP1 key."""
    entries = lexicon.lookup(word)
    assert entries
    assert all(e.key == "rAma" for e in entries)


def test_devanagari_and_slp1_agree():
    assert [e.text for e in lexicon.lookup("योग")] == [
        e.text for e in lexicon.lookup("yoga")
    ]


def test_etymology_source_promotes_its_own_columns():
    """SKD keeps linga/vyutpatti in .fields rather than flattening them away."""
    entries = lexicon.lookup("aMSaH", sources=["skd"])
    assert entries
    e = entries[0]
    assert e.source == "skd" and e.source_name == "Śabdakalpadruma"
    assert e.text  # drawn from the vyutpatti column
    assert e.fields.get("linga") == "puM"


def test_gloss_source_uses_text_column():
    entries = lexicon.lookup("rAma", sources=["abhidhanaratnamala"])
    assert entries and all(e.text for e in entries)


def test_source_filter_restricts_results():
    all_entries = lexicon.lookup("rAma")
    vcp_only = lexicon.lookup("rAma", sources=["vcp"])
    assert vcp_only
    assert len(vcp_only) < len(all_entries)
    assert {e.source for e in vcp_only} == {"vcp"}


def test_repeated_keys_are_all_returned():
    """A headword can appear several times in one table; none are dropped."""
    entries = lexicon.lookup("rAma", sources=["abhidhanacintamani"])
    assert len(entries) > 1


def test_unknown_word_returns_empty():
    assert lexicon.lookup("qqqqqqzzzz") == []


def test_empty_word_returns_empty():
    assert lexicon.lookup("") == []
    assert lexicon.lookup("   ") == []


def test_unknown_source_raises():
    with pytest.raises(KeyError, match="unknown Layer B source"):
        lexicon.lookup("rAma", sources=["nosuchdict"])
    with pytest.raises(KeyError, match="unknown Layer B source"):
        lexicon.is_available("nosuchdict")


def test_entries_never_carry_promoted_columns_in_fields():
    for e in lexicon.lookup("rAma"):
        assert not {"key", "page", "lnum"} & set(e.fields)


def test_is_available_per_source():
    assert lexicon.is_available("skd") is True
    assert lexicon.is_available() is True
