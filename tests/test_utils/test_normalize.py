"""Tests for script detection and SLP1 normalization.

Regression coverage for the word-initial-capital SLP1 ambiguity: the
runner feeds engines already-normalized SLP1, but engines re-detect
the script. Title-case SLP1 like "Bavati" (bhavati) has no interior
uppercase or SLP1-exclusive lowercase, so detect_script falls back to
IAST and a second IAST->SLP1 pass destroys the aspirate ("bavati").
Callers that know their plain-ASCII input is SLP1 pass
plain_ascii_default=Script.SLP1 to resolve the ambiguity.
"""

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.normalize import detect_script, normalize_slp1, strip_nukta
from tests._cases import check_cases

# (id, text, plain_ascii_default or None, expected script)
DETECT_CASES = [
    ("devanagari", "राम", None, Script.DEVANAGARI),
    ("iast_diacritics", "rāma", None, Script.IAST),
    ("slp1_interior_uppercase", "rAma", None, Script.SLP1),
    ("slp1_exclusive_C", "gacCati", None, Script.SLP1),
    ("slp1_exclusive_f", "vftti", None, Script.SLP1),
    ("plain_ascii_defaults_to_iast", "bhavati", None, Script.IAST),
    # Ambiguous: IAST proper noun ("Rama") or SLP1 aspirate ("Bavati").
    # Without a caller hint, plain ASCII stays IAST.
    ("word_initial_capital_defaults_to_iast", "Rama", None, Script.IAST),
    ("hint_resolves_title_case_slp1", "Bavati", Script.SLP1, Script.SLP1),
    ("hint_resolves_plain_ascii", "bhavati", Script.SLP1, Script.SLP1),
    ("hint_ignored_for_devanagari", "राम", Script.SLP1, Script.DEVANAGARI),
    ("hint_ignored_for_iast_diacritics", "rāma", Script.SLP1, Script.IAST),
    ("hint_ignored_for_unambiguous_slp1", "rAma", Script.IAST, Script.SLP1),
    ("devanagari_sentence", "योगश्चित्तवृत्तिनिरोधः", None, Script.DEVANAGARI),
    ("iast_sentence", "yogaścittavṛttinirodhaḥ", None, Script.IAST),
    # SLP1 unique markers: w (ṭ), S (ṣ), z (ś), N (ṇ). Plain "rAma" without a
    # marker is covered by the interior-uppercase row above.
    ("slp1_marker_S", "yogaScittavRttinirodaH", None, Script.SLP1),
    ("slp1_marker_z", "rAmazca", None, Script.SLP1),
    ("slp1_marker_w", "pawati", None, Script.SLP1),
    # Mid-word SLP1 capital aspirates / vocalic liquids regressed the engine:
    # read as IAST, re-transliterated and corrupted (C -> c, f -> P0). The
    # gacCati (C = छ) case is slp1_exclusive_C above.
    ("slp1_vocalic_f", "cittavftti", None, Script.SLP1),
    ("slp1_visarga_then_aspirate_K", "duHKa", None, Script.SLP1),
    ("plain_lowercase_aspirate_is_iast", "gacchati", None, Script.IAST),
    ("empty_defaults_to_slp1", "", None, Script.SLP1),
    ("whitespace_defaults_to_slp1", "   ", None, Script.SLP1),
]

# A run of 3+ ASCII uppercase letters is an acronym, never SLP1.
ACRONYM_CASES = [
    ("acronym_JSON", "JSON"),
    ("acronym_USA", "USA"),
    ("acronym_KGB", "KGB"),
    ("acronym_inside_word", "isJSON"),
]


def test_detect_script() -> None:
    def check(text, hint, expected):
        kwargs = {} if hint is None else {"plain_ascii_default": hint}
        assert detect_script(text, **kwargs) == expected

    check_cases(DETECT_CASES, check)
    check_cases(ACRONYM_CASES, lambda text: _not_slp1(detect_script(text)))


def _not_slp1(script: Script) -> None:
    assert script != Script.SLP1, script


# (id, text, source script or None to auto-detect, expected SLP1)
NORMALIZE_CASES = [
    ("iast_keeps_aspirate", "bhavati", Script.IAST, "Bavati"),
    ("devanagari", "योगः", Script.DEVANAGARI, "yogaH"),
    ("slp1_hint_unchanged", "rAma", Script.SLP1, "rAma"),
    ("auto_detects_devanagari", "राम", None, "rAma"),
    ("auto_detects_iast", "rāma", None, "rAma"),
    ("empty", "", None, ""),
    # ISO 15919 variants (ṁ, r̥, ē) are read as their IAST equivalents.
    ("iso_anusvara_m_dot_above", "saṁskṛtam", None, "saMskftam"),
    ("iso_vocalic_r_ring_below", "kr̥ṣṇa", None, "kfzRa"),
    ("iso_long_vocalic_r", "pitr̥̄n", None, "pitFn"),
    ("iso_vocalic_l", "kl̥ptam", None, "kxptam"),
    ("iso_long_e_macron", "dēva", None, "deva"),
    # A nukta in Sanskrit text is a typo and must never reach SLP1. पितृ़णां
    # (for पितॄणां) appears 37 times in the Valmiki Ramayana; transliteration
    # passed U+093C through, leaving a multi-byte Devanagari character inside
    # ASCII SLP1, which panicked vidyut's Rust splitter mid-character.
    ("nukta_typo_leaves_no_devanagari", "पितृ़णां", None, "pitfRAM"),
    # ड़ (U+095C) decomposes to ड + U+093C, so it normalizes like ड.
    ("precomposed_nukta_letter_falls_back_to_base", "ड़", None, normalize_slp1("ड")),
]


# (id, text, expected) for strip_nukta on its own.
STRIP_NUKTA_CASES = [
    ("combining_nukta_typo", "पितृ़णां", "पितृणां"),
    ("precomposed_dda_decomposes", "ड़", "ड"),
    ("precomposed_qa_decomposes", "क़मल", "कमल"),
    ("no_nukta_unchanged", "पितॄणां", "पितॄणां"),
    ("slp1_unchanged", "rAmaH", "rAmaH"),
    ("empty", "", ""),
]

def test_normalize_slp1() -> None:
    def check(text, script, expected):
        got = normalize_slp1(text) if script is None else normalize_slp1(text, script)
        assert got == expected, got

    check_cases(NORMALIZE_CASES, check)

    def check_strip(text, expected):
        assert strip_nukta(text) == expected

    check_cases(STRIP_NUKTA_CASES, check_strip)


def test_engines_do_not_mangle_runner_slp1() -> None:
    """Engines receive SLP1 from the runner and must not re-detect it as IAST."""
    from sanskrit_analyzer.engines.local_byt5_engine import LocalByT5Engine
    from sanskrit_analyzer.engines.vidyut_engine import VidyutEngine

    vidyut = VidyutEngine.__new__(VidyutEngine)  # skip data-path init
    byt5 = LocalByT5Engine.__new__(LocalByT5Engine)
    cases = [
        ("vidyut_idempotent_title_case", vidyut._normalize_to_slp1, "Bavati", "Bavati"),
        ("vidyut_idempotent_sentence", vidyut._normalize_to_slp1,
         "yogaScittavfttiniroDaH", "yogaScittavfttiniroDaH"),
        ("byt5_reads_plain_ascii_as_slp1", byt5._normalize_to_iast, "Bavati", "bhavati"),
    ]

    def check(fn, text, expected):
        assert fn(text) == expected

    check_cases(cases, check)
