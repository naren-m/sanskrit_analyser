"""Ground truth: roots of the Yoga Sutras' core technical vocabulary.

Every entry is a term whose derivation the grammatical tradition agrees on
(Vyāsa's bhāṣya, MW's etymologies, the Dhātupāṭha). This is the regression
guard for DhatuResolver resolving from the Kośa alone, with no dictionary:
root identification is a ranking problem over homographic Kośa readings, and
a change that helps one word easily breaks another, so the whole set runs
together. The dictionary-assisted path (MW's etymology fed in as
``preferred_root``) is the consuming application's concern, via
``DhatuIdentifier(preferred_root_fn=...)`` — its own golden test covers that.

Roots are SLP1. ``None`` means the word must show NO root — a pronoun,
particle, or a stem with no accepted verbal derivation.
"""

import pytest

from sanskrit_analyzer.dhatu.resolver import get_dhatu_resolver

# (stem in SLP1, expected root in SLP1 or None)
GOLDEN_TERMS = [
    # --- headline derivations, sutra 1.1-1.2 ---
    ("yoga", "yuj"),          # yoking, union
    ("citta", "cit"),         # mind-stuff <- to perceive
    ("vftti", "vft"),         # turning, modification
    ("niroDa", "ruD"),        # ni + to obstruct
    ("anuSAsana", "SAs"),     # anu + to instruct
    # --- the kleśas and their kin (2.3ff) ---
    ("avidyA", "vid"),        # not-knowing; NOT vi + √dā
    pytest.param("rAga", "raYj", marks=pytest.mark.xfail(
        reason="needs MW's 'fr. √rañj' via preferred_root; the Kośa's own "
               "readings (√rāj, √rag, √rañj) do not separate them",
        strict=False)),
    ("dveza", "dviz"),        # aversion
    ("kleSa", "kliS"),        # affliction
    ("aBiniveSa", "viS"),     # abhi + ni + to enter
    # --- practice vocabulary ---
    ("aByAsa", "as"),         # abhi + to be: repeated practice
    pytest.param("vErAgya", "raYj", marks=pytest.mark.xfail(
        reason="taddhita vrddhi stem: no Kosa derivation, MW cites no root",
        strict=False)),
    ("smfti", "smf"),         # memory
    ("samADi", "DA"),         # sam + ā + to place
    ("DAraRA", "Df"),         # to hold
    pytest.param("prARa", "an", marks=pytest.mark.xfail(
        reason="prefix-free root pra also attested; no signal separates them",
        strict=False)),
    ("saMyama", "yam"),       # sam + to restrain
    ("tapas", "tap"),         # to burn, austerity
    pytest.param("karman", "kf", marks=pytest.mark.xfail(
        reason="Kośa has no derivational entry; only the dictionary's cited "
               "root reaches √kṛ, via describe_root(preferred_root)",
        strict=False)),
    ("jAti", "jan"),          # birth <- to be born
    pytest.param("BOga", "Buj", marks=pytest.mark.xfail(
        reason="no Kosa derivation for bhoga, MW cites no root",
        strict=False)),
    ("jYAna", "jYA"),         # knowledge
    ("viveka", "vic"),        # vi + to separate: discernment
    ("KyAti", "KyA"),         # to declare, discernment
    pytest.param("Ananda", "nand", marks=pytest.mark.xfail(
        reason="Kosa cites this root as tunadi~; restoring the idit nasal "
               "infix (P. 7.1.58) is not implemented",
        strict=False)),
    ("saMskAra", "kf"),       # sam + to do: latent impression
    ("Agama", "gam"),         # ā + to go: received testimony
    ("anumAna", "mA"),        # anu + to measure: inference
    ("vyAKyA", "KyA"),        # vi + ā + to declare
    pytest.param("Apatti", "pad", marks=pytest.mark.xfail(
        reason="Kosa offers curated pat over uncurated pad",
        strict=False)),
    # --- Dhātupāṭha citation spellings that must be undone (P. 8.4.41) ---
    ("sTiti", "sTA"),         # cited as ṣṭhā, not sṭhā
    ("avasTA", "sTA"),        # ava + √sthā
    ("vyutTAna", "sTA"),      # vi + ud + √sthā
    ("svapna", "svap"),       # cited as ñiṣvap
    ("prasAda", "sad"),       # pra + √sad, cited as ṣad
    ("naSa", "naS"),       # cited as ṇaś
    # --- words that must stay root-less ---
    ("tad", None),            # pronoun
    ("aTa", None),            # particle
    ("ca", None),             # particle
    ("tatra", None),          # indeclinable
    ("iti", None),            # particle
]


def _ids(terms):
    """Readable test ids for plain tuples and xfail-marked params alike."""
    return [t.values[0] if hasattr(t, "values") else t[0] for t in terms]


@pytest.fixture(scope="module")
def resolve_root():
    """Resolve with the Kośa alone — no dictionary.

    The consuming application supplies MW's etymology through
    DhatuIdentifier(preferred_root_fn=...); two terms below need it and
    are marked xfail here accordingly.
    """
    r = get_dhatu_resolver()
    if not r._ensure():
        pytest.skip("vidyut Kośa unavailable")

    def _resolve(stem):
        info = r.resolve(stem, stem)
        return info["root_slp1"] if info else None

    return _resolve


@pytest.mark.parametrize("stem,expected", GOLDEN_TERMS, ids=_ids(GOLDEN_TERMS))
def test_golden_root(resolve_root, stem, expected):
    got = resolve_root(stem)
    assert got == expected, f"{stem}: expected {expected}, got {got}"
