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


def test_words_split_on_punctuation_keep_avagraha():
    cases = [
        # avagraha is sandhi evidence (rAmo 'sti) — must survive normalization
        ("रामो ऽस्ति", ["rAmo", "'sti"]),
        # only '.' used to be stripped, leaving "rAmaH," and '"vanam"' as words
        ('रामः, गच्छति; "वनम्"', ["rAmaH", "gacCati", "vanam"]),
        ("rāmaḥ—vanam!", ["rAmaH", "vanam"]),
        # non-ASCII left by transliteration panics vidyut downstream
        ("धर्म\u200dक्षेत्रे पितृ़णां", ["Darmakzetre", "pitfRAM"]),
    ]
    failures = [
        f"{text!r}: {normalize(text).words} != {words}"
        for text, words in cases
        if normalize(text).words != words
    ]
    assert not failures, failures


def test_leading_capital_slp1_not_lowercased():
    # "Bavati" is SLP1 (word-initial aspirate Ba), not an IAST proper noun.
    n = normalize("Bavati")
    assert n.script == "slp1"
    assert n.words == ["Bavati"]


def test_empty_input():
    n = normalize("   ")
    assert n.words == [] and n.slp1 == ""
