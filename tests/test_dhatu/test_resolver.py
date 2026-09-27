"""Tests for DhatuResolver — vidyut-Kośa root recovery.

Skips gracefully when the vidyut data bundle is absent (e.g. minimal CI
without the data bundle).
"""
import pytest

from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver
from tests._cases import check_cases


@pytest.fixture(scope="module")
def resolver():
    r = get_dhatu_resolver()
    if not r._ensure():
        pytest.skip("vidyut Kośa unavailable")
    return r


# (row id, surface, stem, expected fields; None means resolve() returns None)
RESOLVE_CASES = [
    # yoga (a nominal stem, not a verb) -> √yuj with its gaṇa + gloss.
    ("derived-noun-yoga-maps-to-yuj-curadi", "yogaH", "yoga",
     {"root_slp1": "yuj", "verified": True, "gana": 10, "is_verb": False}),
    ("prefixed-derivative-nirodha-keeps-ni", "niroDaH", "niroDa",
     {"root_slp1": "ruD", "prefixes_slp1": ["ni"]}),
    # A finite form resolves to its root and is flagged a verb. Also: when only
    # the surface resolves, √bhū lives in bhavati, not in any nominal reading
    # of the stem, so a finite verb still wins from its surface.
    ("finite-verb-bhavati-flagged-bhvadi", "Bavati", "BU",
     {"root_slp1": "BU", "is_verb": True, "gana": 1}),
    # draṣṭṛ -> √dṛś (residual it-marker stripped, curated-verified).
    ("retroflex-drazwf-cleaned-to-dfS", "drazwf", "drazwf", {"root_slp1": "dfS"}),
    # Indeclinables/particles legitimately return None; a peelable-looking
    # indeclinable must still return None after upasarga peeling.
    ("particle-aTa-has-no-root", "aTa", "aTa", None),
    ("peeling-never-fires-on-api", "api", "api", None),
    ("peeling-never-fires-on-tatra", "tatra", "tatra", None),
    # The Kośa files upasarga-prefixed stems as *Basic* pratipādikas with no
    # dhātu link, while the bare derivative is a Kṛdanta that has one. Peeling
    # a canonical upasarga recovers the root and reports the prefix.
    # anuśāsana ('teaching', sutra 1.1) -> anu + √śās.
    ("upasarga-peel-anuSAsana-anu-SAs", "anuSAsanam", "anuSAsana",
     {"root_slp1": "SAs", "prefixes_slp1": ["anu"]}),
    # kliṣṭa -> √kliś, and the lemma kliś *is* that root: a surface-only
    # reading is kept when its root underlies the lemma.
    ("surface-root-underlying-lemma-kept", "klizwa", "kliS", {"root_slp1": "kliS"}),
    # Several Kṛdanta entries can share a stem; first-wins picks wrong roots.
    # vidyā 'knowledge' is √vid 'know', not vi + √dā 'give'.
    ("vidyA-is-vid-not-vi-dA", "vidyA", "vidyA",
     {"root_slp1": "vid", "prefixes_slp1": []}),
    # kāra 'doing' is √kṛ, not √kṝ 'scatter'.
    ("kAra-is-kf-not-kF", "kAra", "kAra", {"root_slp1": "kf"}),
]


def test_resolve(resolver):
    def check(surface, stem, expected):
        info = resolver.resolve(surface, stem)
        if expected is None:
            assert info is None, info
            return
        assert info is not None
        for field, value in expected.items():
            assert info[field] == value, (field, info[field], value)

    check_cases(RESOLVE_CASES, check)

    # The yoga reading carries a gloss (saMyamane).
    assert resolver.resolve("yogaH", "yoga")["artha_slp1"]
    # akliṣṭa ('un-afflicted', sutra 1.5) -> √kliś; a- is not a prefix.
    info = resolver.resolve("aklizwAH", "aklizwa")
    assert info is not None
    assert info["root_slp1"] == "kliS"
    assert "a" not in info["prefixes_slp1"]
    # viṣayam matched a vi+√siv 'to sew' krdanta; viṣaya is not from √siv, and
    # the word's other occurrences do not say so: a root foreign to the lemma
    # is discarded.
    info = resolver.resolve("vizayam", "vizaya")
    assert info is None or info["root_slp1"] != "siv"


def test_citation_spelled_index_keys(resolver):
    """The Dhātupāṭha indexes roots under their *citation* spelling: an initial
    s is written ṣ and an initial n is written ṇ (P. 6.1.64-65 read in
    reverse), so √sidh is filed as ṣidh. Normalising the spelling before the
    index lookup asks for a key that does not exist, so a real root comes back
    unverified — and the adapter drops unverified roots. 90 of the index's 97
    citation-spelled roots are reachable only under the cited key."""
    # siddhi -> √sidh, attested (filed as ṣidh 01.0450 'gatyām').
    info = resolver.resolve("sidDi")
    assert info is not None
    assert info["root_slp1"] == "siD"
    assert info["verified"] is True, "√sidh is in the Dhātupāṭha as ṣidh"
    assert info["gana"] == 1
    assert info["artha_slp1"]
    # Verification via the cited key must not leak ṣ/ṇ into the output.
    assert not info["root_slp1"].startswith(("z", "R"))
    # describe_root (yoga_sutras' fallback for a dictionary-named root)
    # did an exact index lookup: √sidh/√sic missed, √nah came back as ṇah.
    for root in ("siD", "sic", "nah"):
        described = resolver.describe_root(root)
        assert described and described["root_slp1"] == root, (root, described)


# (row id, aupadeśika, expected clean root; must verify)
CLEAN_ROOT_CASES = [
    # _clean_root reports the real spelling but must still verify.
    ("citation-spelled-zi-Du-finds-siD-under-cited-key", "zi\\Du~", "siD"),
    # Some roots carry an it-marker *before* the root (P. 1.3.2ff): √hā is
    # cited ohāk, √vij is ovijī. The marker's tilde looks exactly like the tail
    # of a trailing nasal-infix residue (rudhi~), so stripping the residue first
    # consumes the whole root and leaves the bare marker vowel. Twelve
    # Dhātupāṭha roots are lost that way, √hā 'to abandon' among them.
    ("leading-o-marker-ohAk-keeps-hA-before-residue-rule", "o~hA\\k", "hA"),
    # The index files some of these keeping the marker (core_root o~vij).
    ("leading-marker-o-vij-verifies-under-index-key", "o~vijI~\\", "vij"),
    # Task 2 fixed the ghu- case at source: √ghuṇ keeps its initial and
    # verifies (it used to be filed under 'ṇ').
    ("ghu-root-GuRa-resolves-properly-task-2", "GuRa~", "GuR"),
    # √i and √ṛ are genuine one-letter roots.
    ("single-vowel-root-i-survives", "i\\N", "i"),
    ("single-vowel-root-f-survives", "f\\", "f"),
]


def test_clean_root(resolver):
    def check(aupadeshika, expected):
        root, verified, _curated = resolver._clean_root(aupadeshika)
        assert root == expected
        assert verified is True

    check_cases(CLEAN_ROOT_CASES, check)

    # No single marker vowel may ever be reported as a dhātu.
    for aupadeshika in ("o~hA\\N", "o~vE\\", "wuo~Svi", "o~vrascU~"):
        root, _, _ = resolver._clean_root(aupadeshika)
        assert root not in ("o", "u", ""), f"{aupadeshika} collapsed to {root!r}"

    # The Dhātupāṭha index used to reduce a few roots to a single consonant.
    # No Sanskrit root is a bare consonant, so the bare-consonant guard stays as
    # defence in depth — better shown as nothing than as a confident √n.
    assert not resolver._is_plausible_root("n")
    assert not resolver._is_plausible_root("z")
    assert not resolver._is_plausible_root("-")
    assert resolver._clean_root("-")[0] != "-" or not resolver._clean_root("-")[1]


# Ground truth: roots of the Yoga Sutras' core technical vocabulary.
#
# Every entry is a term whose derivation the grammatical tradition agrees on
# (Vyāsa's bhāṣya, MW's etymologies, the Dhātupāṭha). This is the regression
# guard for DhatuResolver resolving from the Kośa alone, with no dictionary:
# root identification is a ranking problem over homographic Kośa readings, and
# a change that helps one word easily breaks another, so the whole set runs
# together. The dictionary-assisted path (MW's etymology fed in as
# ``preferred_root``) is the consuming application's concern, via
# ``DhatuIdentifier(preferred_root_fn=...)`` — its own golden test covers that.
#
# Roots are SLP1. ``None`` means the word must show NO root — a pronoun,
# particle, or a stem with no accepted verbal derivation.
# (stem in SLP1, expected root in SLP1 or None); the stem is the row id.
GOLDEN_TERMS = [
    # --- headline derivations, sutra 1.1-1.2 ---
    ("yoga", "yuj"),          # yoking, union
    ("citta", "cit"),         # mind-stuff <- to perceive
    ("vftti", "vft"),         # turning, modification
    ("niroDa", "ruD"),        # ni + to obstruct
    ("anuSAsana", "SAs"),     # anu + to instruct
    # --- the kleśas and their kin (2.3ff) ---
    ("avidyA", "vid"),        # not-knowing; NOT vi + √dā
    ("rAga", "raYj"),
    ("dveza", "dviz"),        # aversion
    ("kleSa", "kliS"),        # affliction
    ("aBiniveSa", "viS"),     # abhi + ni + to enter
    # --- practice vocabulary ---
    ("aByAsa", "as"),         # abhi + to be: repeated practice
    ("vErAgya", "raYj"),
    ("smfti", "smf"),         # memory
    ("samADi", "DA"),         # sam + ā + to place
    ("DAraRA", "Df"),         # to hold
    # Was a non-strict xfail ("prefix-free root pra also attested; no signal
    # separates them") that passes deterministically; now pinned as passing.
    ("prARa", "an"),
    ("saMyama", "yam"),       # sam + to restrain
    ("tapas", "tap"),         # to burn, austerity
    ("karman", "kf"),
    ("jAti", "jan"),          # birth <- to be born
    ("BOga", "Buj"),
    ("jYAna", "jYA"),         # knowledge
    ("viveka", "vic"),        # vi + to separate: discernment
    ("KyAti", "KyA"),         # to declare, discernment
    ("Ananda", "nand"),
    ("saMskAra", "kf"),       # sam + to do: latent impression
    ("Agama", "gam"),         # ā + to go: received testimony
    ("anumAna", "mA"),        # anu + to measure: inference
    ("vyAKyA", "KyA"),        # vi + ā + to declare
    ("Apatti", "pad"),
    # --- Dhātupāṭha citation spellings that must be undone (P. 8.4.41) ---
    ("sTiti", "sTA"),         # cited as ṣṭhā, not sṭhā
    ("avasTA", "sTA"),        # ava + √sthā
    ("vyutTAna", "sTA"),      # vi + ud + √sthā
    ("svapna", "svap"),       # cited as ñiṣvap
    ("prasAda", "sad"),       # pra + √sad, cited as ṣad
    ("naSa", "naS"),          # cited as ṇaś
    # --- words that must stay root-less ---
    ("tad", None),            # pronoun
    ("aTa", None),            # particle
    ("ca", None),             # particle
    ("tatra", None),          # indeclinable
    ("iti", None),            # particle
]

# Known gaps resolving from the Kośa alone. The consuming application supplies
# MW's etymology through DhatuIdentifier(preferred_root_fn=...); these need it.
GOLDEN_GAPS = {
    "rAga": "needs MW's 'fr. √rañj' via preferred_root; the Kośa's own "
            "readings (√rāj, √rag, √rañj) do not separate them",
    "vErAgya": "taddhita vrddhi stem: no Kosa derivation, MW cites no root",
    "karman": "Kośa has no derivational entry; only the dictionary's cited "
              "root reaches √kṛ, via describe_root(preferred_root)",
    "BOga": "no Kosa derivation for bhoga, MW cites no root",
    "Ananda": "Kosa cites this root as tunadi~; restoring the idit nasal "
              "infix (P. 7.1.58) is not implemented",
    "Apatti": "Kosa offers curated pat over uncurated pad",
}


def test_golden_roots(resolver):
    """Resolve with the Kośa alone — no dictionary."""

    def check(expected, stem):
        info = resolver.resolve(stem, stem)
        got = info["root_slp1"] if info else None
        assert got == expected, f"{stem}: expected {expected}, got {got}"

    rows = [(stem, expected, stem) for stem, expected in GOLDEN_TERMS]
    check_cases(rows, check, xfail=GOLDEN_GAPS)
