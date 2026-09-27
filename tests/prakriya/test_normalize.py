"""Input normalization: any script -> clean SLP1 word list."""
from sanskrit_analyzer.prakriya.normalize import normalize
from tests._cases import check_cases

# (id, input, expected words, expected script or None to skip, expected slp1 or None)
WORD_CASES = [
    ("devanagari-to-slp1", "भवति", ["Bavati"], "devanagari", "Bavati"),
    # "Bavati" is SLP1 (word-initial aspirate Ba), not an IAST proper noun.
    ("leading-capital-slp1-not-lowercased", "Bavati", ["Bavati"], "slp1", None),
    ("empty-input", "   ", [], None, ""),
    # avagraha is sandhi evidence (rAmo 'sti) — must survive normalization
    ("avagraha-kept", "रामो ऽस्ति", ["rAmo", "'sti"], None, None),
    # only '.' used to be stripped, leaving "rAmaH," and '"vanam"' as words
    ("comma-semicolon-quotes-stripped", 'रामः, गच्छति; "वनम्"',
     ["rAmaH", "gacCati", "vanam"], None, None),
    ("em-dash-and-bang-split", "rāmaḥ—vanam!", ["rAmaH", "vanam"], None, None),
    # non-ASCII left by transliteration panics vidyut downstream
    ("zwj-and-nukta-removed", "धर्म‍क्षेत्रे पितृ़णां",
     ["Darmakzetre", "pitfRAM"], None, None),
]


def test_normalize_words():
    def check(text, words, script, slp1):
        n = normalize(text)
        assert n.words == words
        if script is not None:
            assert n.script == script
        if slp1 is not None:
            assert n.slp1 == slp1

    check_cases(WORD_CASES, check)


def test_iast_verse_with_dandas_and_verse_number():
    n = normalize("dharmakṣetre kurukṣetre māmakāḥ pāṇḍavāś ca । १.१ ॥")
    assert n.words[0] == "Darmakzetre"
    assert "॥" not in n.slp1 and "।" not in n.slp1
    assert not any(w.strip(".|0123456789") == "" for w in n.words)
