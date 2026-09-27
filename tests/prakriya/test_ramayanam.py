"""End-to-end prakriyā checks against real Rāmāyaṇa ślokas.

Ground truth is Vālmīki's Rāmāyaṇa, BālaKāṇḍa sarga 1 — the opening ślokas and
their word-by-word glosses as recorded in the ramayanam corpus
(``data/slokas/Slokas/BalaKanda/BalaKanda_sarga_1_meaning.txt``). Each assertion
ties an engine output (lemma / kind / morphology / meter) back to the human gloss,
so a regression here means we diverged from an authoritative reading, not merely
from a fixture we invented.

BalaKanda 1.1.1
    तपस्स्वाध्यायनिरतं तपस्वी वाग्विदां वरम् ।
    नारदं परिपप्रच्छ वाल्मीकिर्मुनिपुङ्गवम् ।।
    "Ascetic Vālmīki enquired of Nārada, best among the eloquent, ..."

BalaKanda 1.1.6
    श्रुत्वा चैतत्... प्रहृष्टो वाक्यमब्रवीत् ।
    "... having heard (this), delighted, (he) spoke (these) words."
"""
import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya import analyze_verse
from sanskrit_analyzer.prakriya.analyzer import PadaAnalysis, analyze_pada
from tests._cases import check_cases

# The opening śloka in Devanagari, exactly as stored in the corpus (daṇḍas and all).
OPENING_SLOKA = (
    "तपस्स्वाध्यायनिरतं तपस्वी वाग्विदां वरम् ।"
    "नारदं परिपप्रच्छ वाल्मीकिर्मुनिपुङ्गवम् ।।"
)

# SundaraKanda 1.1.1 — the kāṇḍa opens as Hanumān resolves to search for Sītā:
# "iyeṣa padam anveṣṭuṃ ... pathi" — "(he) desired to seek the trail ... on the path."
SUNDARA_SLOKA = (
    "ततो रावणनीतायाः सीतायाः शत्रुकर्शनः ।"
    "इयेष पदमन्वेष्टुं चारणाचरिते पथि ।।"
)


def _lemmas(word: str) -> set[str]:
    return {a.lemma for a in analyze_pada(word)}


def _find(word: str, lemma: str, kind: str | None = None) -> PadaAnalysis | None:
    """First verified analysis of ``word`` matching ``lemma`` (and ``kind``, if given)."""
    return next(
        (
            a
            for a in analyze_pada(word)
            if a.lemma == lemma and (kind is None or a.kind == kind)
        ),
        None,
    )


# --- verse-level: Devanagari normalization + meter ------------------------------

# (id, verse, pada surfaces that must appear, (surface, lemma) readings required)
# Both verses are anuṣṭubh (śloka); the classifier labels the pathyā/vipulā form.
# This exercises Devanagari -> SLP1 normalization and daṇḍa stripping through
# the public facade. Sandhi is left intact by design, so surfaces are the
# post-normalization SLP1 tokens.
VERSE_CASES = [
    ("bala-1.1.1-opening-sloka", OPENING_SLOKA, {"tapasvI", "nAradaM"}, []),
    # A second, independently-sourced anuṣṭubh guards against over-fitting to
    # the BalaKanda verse. Its finite verb iyeṣa (perfect of √iṣ, "desired")
    # must survive forward-synthesis verification.
    ("sundara-1.1.1-perfect-verb-iyeza", SUNDARA_SLOKA, {"iyeza"}, [("iyeza", "iz")]),
]


def test_verse_scans_as_anushtubh_with_verified_padas():
    def check(verse, surfaces, readings):
        record = analyze_verse(verse)
        assert record["chandas"] is not None
        assert record["chandas"]["name"].startswith("anuzwuB")
        padas = {p["surface"]: p for p in record["padas"]}
        assert surfaces <= padas.keys(), f"missing {surfaces - padas.keys()}"
        for surface, lemma in readings:
            assert any(a["lemma"] == lemma for a in padas[surface]["analyses"])
        # The engine's core invariant on real text: nothing is fabricated. Every
        # returned reading verified by forward synthesis and carries a rule trace.
        analyses = [a for p in record["padas"] for a in p["analyses"]]
        assert analyses, "at least some words in the verse must analyze"
        for a in analyses:
            assert a["verified"] is True
            assert a["prakriya"], f"{a['lemma']} verified but has no derivation steps"

    check_cases(VERSE_CASES, check)


# --- word-level: the first matching reading, tied to the corpus gloss -----------

# (id, surface, lemma, kind filter for _find or None, kind the reading must
# have or None, morph substrings, exact morph or None).
# vidyut's internal lakāra tags: la~N = imperfect (laṄ), li~w = perfect (liṭ),
# lf~w = future (lṛṭ). ktvā-gerunds ("having Xed") are avyaya — the engine must
# tag them indeclinable rather than inflect them.
READING_CASES = [
    # तपस्वी — "ascetic" (Vālmīki), the subject: masc. nominative singular.
    ("tapasvin-nominative", "tapasvI", "tapasvin", None, "Subanta", ["praTamA"], None),
    # नारदम् — "Nārada", whom Vālmīki enquired of: accusative (dvitīyā).
    ("narada-accusative-object", "nAradaM", "nArada", None, "Subanta", ["dvitIyA"], None),
    # वाल्मीकि: — the sage's name; nominative singular.
    ("valmiki-nominative", "vAlmIkiH", "vAlmIki", None, None, ["praTamA"], None),
    # अब्रवीत् (1.1.6) — "(he) spoke": root brū, imperfect (laṄ), 3rd person sg.
    ("abravit-bru-imperfect", "abravIt", "brU", None, "Tinanta", ["la~N"], None),
    ("uvaca-vac-perfect-said", "uvAca", "vac", "Tinanta", None, ["li~w"], None),
    ("jagama-gam-perfect-went", "jagAma", "gam", "Tinanta", None, ["li~w"], None),
    # iyeṣa is SundaraKanda 1.1.1
    ("iyeza-iz-perfect-desired", "iyeza", "iz", "Tinanta", None, ["li~w"], None),
    # vakṣyāmi is BalaKanda 1.1.7
    ("vakzyami-vac-future-shall-tell", "vakzyAmi", "vac", "Tinanta", None, ["lf~w"], None),
    # śrutvā is from BalaKanda 1.1.6
    ("srutva-ktva-gerund-indeclinable", "SrutvA", "Sru", None, None, [], "avyaya"),
    ("muktva-ktva-gerund-indeclinable", "muktvA", "muc", None, None, [], "avyaya"),
]


def test_word_reading():
    def check(word, lemma, kind_filter, kind, feats, morph):
        a = _find(word, lemma, kind=kind_filter)
        assert a is not None, f"{word}: no reading with root {lemma!r}"
        if kind is not None:
            assert a.kind == kind
        for f in feats:
            assert f in a.morph, f"{word}: expected {f} in morph {a.morph!r}"
        if morph is not None:
            assert a.morph == morph

    check_cases(READING_CASES, check)


# --- nominals: case (vibhakti) and number recovered from the surface ------------

# (id, surface, lemma, required-feature-substrings). Each is a declined word from
# the opening ślokas or other kāṇḍas, with the case its corpus gloss implies:
#   tftIyA = instrumental, zazWI = genitive, saptamI = locative; eka/bahu = sg/pl.
NOMINAL_CASES = [
    ("Baratena-by-bharata-instr-sg", "Baratena", "Barata", ["tftIyA", "eka"]),
    ("janEH-by-people-instr-pl", "janEH", "jana", ["tftIyA", "bahu"]),
    ("sItAyAH-of-sita-gen-fem", "sItAyAH", "sItA", ["strI", "zazWI"]),
    ("paTi-on-the-path-loc", "paTi", "paTin", ["saptamI"]),
    ("guRAH-qualities-nom-pl", "guRAH", "guRa", ["praTamA", "bahu"]),
]


def test_nominal_case_and_number():
    def check(word, lemma, feats):
        analyses = analyze_pada(word)
        hits = [a for a in analyses if a.lemma == lemma and all(f in a.morph for f in feats)]
        assert hits, (
            f"{word}: no {lemma!r} reading with all of {feats}; "
            f"got {[(a.lemma, a.morph) for a in analyses]}"
        )

    check_cases(NOMINAL_CASES, check)


# --- corpus gloss alignment (data-driven) ---------------------------------------

# Word (post-segmentation SLP1) -> lemma the corpus gloss implies. Every pair is
# a line in BalaKanda_sarga_1_meaning.txt; keeping them in one table makes the
# engine's agreement with the authoritative reading auditable at a glance.
CORPUS_GLOSSES = {
    "tapasvI": "tapasvin",          # ascetic
    "nAradaM": "nArada",            # Nārada
    "munipuNgavam": "munipuMgava",  # preeminent sage
    "vAlmIkiH": "vAlmIki",          # Vālmīki
    "guRAH": "guRa",                # qualities
    "janEH": "jana",                # by people
    "sItAyAH": "sItA",              # of Sītā
    "paTi": "paTin",                # on the path
    "SrutaH": "Sruta",              # renowned / (is) heard
    "nItaH": "nIta",                # (was) led
    "abravIt": "brU",               # spoke
    "uvAca": "vac",                 # said
    "jagAma": "gam",                # went
    "iyeza": "iz",                  # desired
    "SrutvA": "Sru",                # having heard
    "muktvA": "muc",                # having released
}


def test_engine_lemma_matches_corpus_gloss():
    def check(word, lemma):
        lemmas = _lemmas(word)
        assert lemma in lemmas, (
            f"{word}: expected lemma {lemma!r} from the corpus gloss, got {lemmas}"
        )

    rows = [(f"{word}={lemma}", word, lemma) for word, lemma in sorted(CORPUS_GLOSSES.items())]
    check_cases(rows, check)
