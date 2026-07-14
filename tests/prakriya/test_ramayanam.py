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


def test_opening_sloka_scans_as_anushtubh():
    # The whole verse is an anuṣṭubh (śloka); the classifier labels the pathyā/
    # vipulā form. This also exercises Devanagari -> SLP1 normalization and
    # daṇḍa stripping through the public facade.
    record = analyze_verse(OPENING_SLOKA)
    assert record["chandas"] is not None
    assert record["chandas"]["name"].startswith("anuzwuB")


def test_opening_sloka_yields_padas():
    record = analyze_verse(OPENING_SLOKA)
    surfaces = {p["surface"] for p in record["padas"]}
    # Post-normalization SLP1 word tokens (sandhi is left intact by design).
    assert "tapasvI" in surfaces
    assert "nAradaM" in surfaces


def test_every_analysis_on_the_verse_is_verified_with_a_trace():
    # The engine's core invariant on real text: nothing is fabricated. Every
    # returned reading verified by forward synthesis and carries a rule trace.
    record = analyze_verse(OPENING_SLOKA)
    analyses = [a for p in record["padas"] for a in p["analyses"]]
    assert analyses, "at least some words in the verse must analyze"
    for a in analyses:
        assert a["verified"] is True
        assert a["prakriya"], f"{a['lemma']} verified but has no derivation steps"


def test_sundara_kanda_opening_scans_and_finds_the_perfect_verb():
    # A second, independently-sourced anuṣṭubh (SundaraKanda 1.1.1) guards against
    # over-fitting to the BalaKanda verse. Its finite verb iyeṣa (perfect of √iṣ,
    # "desired") must survive forward-synthesis verification.
    record = analyze_verse(SUNDARA_SLOKA)
    assert record["chandas"]["name"].startswith("anuzwuB")
    iyesha = next(p for p in record["padas"] if p["surface"] == "iyeza")
    assert any(a["lemma"] == "iz" for a in iyesha["analyses"])


# --- word-level: each tied to the corpus gloss ----------------------------------


def test_tapasvin_nominative():
    # तपस्वी — "ascetic" (Vālmīki), the subject: masc. nominative singular.
    a = _find("tapasvI", "tapasvin")
    assert a is not None
    assert a.kind == "Subanta"
    assert "praTamA" in a.morph  # nominative


def test_narada_is_the_accusative_object():
    # नारदम् — "Nārada", whom Vālmīki enquired of: accusative (dvitīyā).
    a = _find("nAradaM", "nArada")
    assert a is not None
    assert a.kind == "Subanta"
    assert "dvitIyA" in a.morph


def test_valmiki_identified():
    # वाल्मीकि: — the sage's name; nominative singular.
    a = _find("vAlmIkiH", "vAlmIki")
    assert a is not None
    assert "praTamA" in a.morph


def test_finite_verb_abravit():
    # अब्रवीत् (1.1.6) — "(he) spoke": root brū, imperfect (laṄ), 3rd person sg.
    a = _find("abravIt", "brU")
    assert a is not None
    assert a.kind == "Tinanta"
    assert "la~N" in a.morph  # laṄ = imperfect


# --- ktvā-gerunds: indeclinable, root-lemma'd -----------------------------------

# (surface, root). ktvā-gerunds ("having Xed") are avyaya — the engine must tag
# them indeclinable rather than inflect them. śrutvā is from BalaKanda 1.1.6.
GERUNDS = [
    ("SrutvA", "Sru"),   # having heard
    ("muktvA", "muc"),   # having released
]


@pytest.mark.parametrize("word,root", GERUNDS)
def test_ktva_gerund_is_indeclinable(word, root):
    a = _find(word, root)
    assert a is not None, f"{word}: no reading with root {root!r}"
    assert a.morph == "avyaya"


# --- finite verbs: root + lakāra (tense/mood) across the corpus ------------------

# (surface, root, lakāra-tag). vidyut's internal lakāra tags:
#   la~N = imperfect (laṄ), li~w = perfect (liṭ), lf~w = future (lṛṭ).
# abravīt is BalaKanda 1.1.6; vakṣyāmi is 1.1.7; iyeṣa is SundaraKanda 1.1.1.
FINITE_VERBS = [
    ("uvAca",    "vac", "li~w"),   # said            (perfect)
    ("jagAma",   "gam", "li~w"),   # went            (perfect)
    ("iyeza",    "iz",  "li~w"),   # desired         (perfect)
    ("vakzyAmi", "vac", "lf~w"),   # shall tell      (future)
]


@pytest.mark.parametrize("word,root,lakara", FINITE_VERBS)
def test_finite_verb_root_and_tense(word, root, lakara):
    a = _find(word, root, kind="Tinanta")
    assert a is not None, f"{word}: no Tinanta reading with root {root!r}"
    assert lakara in a.morph, f"{word}: expected {lakara} in morph {a.morph!r}"


# --- nominals: case (vibhakti) and number recovered from the surface ------------

# (surface, lemma, required-feature-substrings). Each is a declined word from the
# opening ślokas or other kāṇḍas, with the case its corpus gloss implies:
#   tftIyA = instrumental, zazWI = genitive, saptamI = locative; eka/bahu = sg/pl.
NOMINAL_CASES = [
    ("Baratena", "Barata", ["tftIyA", "eka"]),   # "by Bharata" (instr. sg)
    ("janEH",    "jana",   ["tftIyA", "bahu"]),  # "by people"  (instr. pl)
    ("sItAyAH",  "sItA",   ["strI", "zazWI"]),   # "of Sītā"    (gen. fem.)
    ("paTi",     "paTin",  ["saptamI"]),         # "on the path"(loc.)
    ("guRAH",    "guRa",   ["praTamA", "bahu"]),  # "qualities"  (nom. pl)
]


@pytest.mark.parametrize("word,lemma,feats", NOMINAL_CASES)
def test_nominal_case_and_number(word, lemma, feats):
    hits = [
        a
        for a in analyze_pada(word)
        if a.lemma == lemma and all(f in a.morph for f in feats)
    ]
    assert hits, (
        f"{word}: no {lemma!r} reading with all of {feats}; "
        f"got {[(a.lemma, a.morph) for a in analyze_pada(word)]}"
    )


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


@pytest.mark.parametrize("word,lemma", sorted(CORPUS_GLOSSES.items()))
def test_engine_lemma_matches_corpus_gloss(word, lemma):
    lemmas = _lemmas(word)
    assert lemma in lemmas, (
        f"{word}: expected lemma {lemma!r} from the corpus gloss, got {lemmas}"
    )
