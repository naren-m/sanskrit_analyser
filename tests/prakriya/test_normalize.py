"""Input normalization: any script -> clean SLP1 word list."""
from sanskrit_analyzer.prakriya.normalize import normalize


def test_devanagari_to_slp1():
    n = normalize("भवति")
    assert n.script == "devanagari"
    assert n.slp1 == "Bavati"
    assert n.words == ["Bavati"]


def test_iast_verse_with_dandas_and_verse_number():
    n = normalize("dharmakṣetre kurukṣetre māmakāḥ pāṇḍavāś ca । १.१ ॥")
    assert n.words[0] == "Darmakzetre"
    assert "॥" not in n.slp1 and "।" not in n.slp1
    assert not any(w.strip(".|0123456789") == "" for w in n.words)


def test_avagraha_preserved():
    # avagraha is sandhi evidence (rAmo 'sti) — must survive normalization
    n = normalize("रामो ऽस्ति")
    assert n.words == ["rAmo", "'sti"]


def test_empty_input():
    n = normalize("   ")
    assert n.words == [] and n.slp1 == ""
