"""Word verification on forms from real verses (needs the vidyut data bundle).

Each row is (surface, ByT5 lemma, ByT5 tag, after mā) -> what the reader must
conclude. Rows come from BG 2.47, BG 18.66, Rām. 1.1.1-2 and the dev-set
failures fixed while building the reader.
"""
from __future__ import annotations

import pytest

pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir  # noqa: E402
from sanskrit_analyzer.reader.derive import verify_word  # noqa: E402
from sanskrit_analyzer.reader.tags import decode  # noqa: E402

pytestmark = pytest.mark.skipif(resolve_data_dir() is None, reason="vidyut data bundle not installed")


@pytest.mark.parametrize(
    ("surface", "lemma", "tag", "after_ma", "kind", "want_lemma", "want_feature", "source"),
    [
        # liṭ with an upasarga (Rām. 1.1.1)
        ("paripapracCa", "paripracC", "SPs3In", False, "tinanta", "pracC", ("upasarga", "pari"), "vidyut"),
        # enclitic te for tava, 8.1.22 (BG 2.47)
        ("te", "tvad", "SG", False, "subanta", "yuzmad", ("vibhakti", "zazWI"), "vidyut+reader-rule"),
        # aorist without augment after mā, 6.4.74 (BG 2.47)
        ("BUH", "BU", "SPs2", True, "tinanta", "BU", ("lakara", "luN"), "vidyut+reader-rule"),
        # avyaya + indefinite particle
        ("kadAcana", "kadAcana", "", False, "avyaya", "kadAcana", ("particle", "cana"), "kosha"),
        # matup taddhita (Rām. 1.1.2)
        ("guRavAn", "guRavat", "SNM", False, "subanta", "guRavat", ("taddhita", "matup"), "vidyut"),
        ("hanumAn", "hanumant", "SNM", False, "subanta", "hanumat", ("taddhita", "matup"), "vidyut"),
        # kta participle with an upasarga
        ("upAgatam", "upAgam", "SNPaNe", False, "subanta", "gam", ("krt", "kta"), "vidyut"),
        # lyap with two upasargas
        ("samutsfjya", "samutsfj", "Co", False, "avyaya", "sfj", ("krt", "lyap"), "vidyut"),
        # -ay lemma: 10th-class muc (mocayati) or causative; either way a kta participle
        ("mocitaH", "mocay", "SNPaM", False, "subanta", "muc", ("krt", "kta"), "vidyut"),
        # sa for saH before a consonant, 6.1.132
        ("sa", "sa", "", False, "subanta", "tad", ("vibhakti", "praTamA"), "vidyut+reader-rule"),
        # active ātmanepada wins over the passive reading of the same surface (BG 2.20)
        ("mriyate", "mf", "SPr3InPv", False, "tinanta", "mf", ("prayoga", "kartari"), "vidyut"),
    ],
)
def test_verified_readings(surface, lemma, tag, after_ma, kind, want_lemma, want_feature,
                           source) -> None:
    r = verify_word(surface, lemma, decode(tag), after_ma=after_ma)
    assert r.verified, r.notes
    assert (r.kind, r.lemma, r.source) == (kind, want_lemma, source)
    assert r.features.get(want_feature[0]) == want_feature[1]


@pytest.mark.parametrize(
    ("surface", "lemma", "tag"),
    [
        ("meripuH", "meripu", "SNM"),        # bad split of me + ripuH: stem is not a word
        ("ArAjan", "ArAjan", "SVM"),         # bad split of rAjA + rAjan
        ("pravivyaDuH", "pravyaD", "PPs3In"),  # epic form; vidyut derives praviviDuH
    ],
)
def test_unverified_stays_unverified(surface: str, lemma: str, tag: str) -> None:
    assert not verify_word(surface, lemma, decode(tag)).verified
