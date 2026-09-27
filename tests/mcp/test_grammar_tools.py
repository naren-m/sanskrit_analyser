"""Tests for MCP grammar tools, dispatched as a client would call them.

Each row names a tool, its arguments, and a check on the decoded reply. The
checks pin real grammar (gam + laṭ -> tip, Śap; ikṣvāku-vaṃśa-prabhavaḥ splits
in three), not response shape.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest

from sanskrit_analyzer.mcp.tools.grammar import build_grammar_tools
from sanskrit_analyzer.vidyut_data import is_available as vidyut_available

needs_vidyut = pytest.mark.skipif(
    not vidyut_available(), reason="vidyut data bundle not available"
)


@pytest.fixture(scope="module")
def dispatch():
    _, dispatcher = build_grammar_tools()
    return dispatcher


def _reply(text: str) -> Any:
    """Decode a JSON reply; plain-text and error replies stay strings."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _reading(reply: list[dict], lemma: str, morph: str) -> dict:
    return next(r for r in reply if r["lemma"] == lemma and r["morph"] == morph)


def _pratyayas(reply: list[dict], lemma: str, morph: str) -> list[tuple[str, str]]:
    return [(p["pratyaya"], p["sutra"]) for p in _reading(reply, lemma, morph)["pratyayas"]]


def _explained(reply: dict, surface: str) -> list[tuple[str, str]]:
    word = next(w for w in reply["words"] if w["surface"] == surface)
    return [(a["lemma"], a["morph"]) for a in word["analyses"]]


def _selected(reply: dict, form: str) -> dict:
    return next(w for w in reply["selected_breakdown"] if w["form"] == form)


Case = tuple[str, str, dict[str, Any], Callable[[Any], bool]]

# (id, tool, arguments, check on the decoded reply)
CASES: list[Case] = [
    # get_pratyaya: pratyayas read off the vidyut-prakriya trace, each with
    # the sūtra that introduced it.
    ("pratyaya-gacchati-lat", "get_pratyaya", {"word": "gacCati"},
     lambda r: _pratyayas(r, "gam", "la~w kartari praTama eka")
     == [("la~w", "3.2.123"), ("tip", "3.4.78"), ("Sap", "3.1.68")]),
    ("pratyaya-gatah-kta", "get_pratyaya", {"word": "gataH"},
     lambda r: _pratyayas(r, "gam", "puM praTamA eka") == [("kta", "3.2.102"), ("su~", "4.1.2")]),
    ("pratyaya-gantum-tumun-devanagari", "get_pratyaya", {"word": "गन्तुम्"},
     lambda r: ("tumu~n", "3.3.10") in _pratyayas(r, "gam", "avyaya")),
    ("pratyaya-niyate-karmani-yak", "get_pratyaya", {"word": "nIyate"},
     lambda r: ("yak", "3.1.67") in _pratyayas(r, "nI", "la~w karmaRi praTama eka")),
    ("pratyaya-karayati-nic-first", "get_pratyaya", {"word": "kArayati"},
     lambda r: _pratyayas(r, "kAri", "la~w kartari praTama eka")[0] == ("Ric", "3.1.26")),
    # laṅ's lakāra is "la" after it-removal, not "l"; tip must still be seen.
    ("pratyaya-abhavat-lan-tip", "get_pratyaya", {"word": "aBavat"},
     lambda r: _pratyayas(r, "BU", "la~N kartari praTama eka")
     == [("laN", "3.2.111"), ("tip", "3.4.78"), ("Sap", "3.1.68")]),
    # yāsuṭ (3.4.103) is an āgama, not a pratyaya.
    ("pratyaya-bhavet-no-agama", "get_pratyaya", {"word": "Bavet"},
     lambda r: [p for p, _ in _pratyayas(r, "BU", "viDili~N kartari praTama eka")]
     == ["li~N", "tip", "Sap"]),
    ("pratyaya-sutra-text-attached", "get_pratyaya", {"word": "gacCati"},
     lambda r: r[0]["pratyayas"][1]["sutra_text"].startswith("tiptasJi")),
    ("pratyaya-gibberish", "get_pratyaya", {"word": "xyzzyq"},
     lambda r: r.startswith("No derivable reading")),
    # explain_parse: every verified reading per word, never a fabricated one.
    ("explain-gacchati-verb-and-participle", "explain_parse", {"text": "रामो गच्छति"},
     lambda r: _explained(r, "gacCati")[:2]
     == [("gam", "la~w kartari praTama eka"), ("gam", "puM saptamI eka")]),
    ("explain-ramo-desandhi", "explain_parse", {"text": "रामो गच्छति"},
     lambda r: ("rAma", "puM praTamA eka") in _explained(r, "rAmo")),
    ("explain-trace-ends-at-surface", "explain_parse", {"text": "Bavati"},
     lambda r: r["words"][0]["analyses"][0]["prakriya"][-1]["form"].replace(" + ", "")
     == "Bavati"),
    ("explain-gibberish-empty", "explain_parse", {"text": "xyzzyq"},
     lambda r: r["words"] == [{"surface": "xyzzyq", "analyses": []}]),
    # identify_compound: members from the kosha-backed segmenter.
    ("compound-ikshvaku", "identify_compound", {"word": "इक्ष्वाकुवंशप्रभवः"},
     lambda r: r[0]["members_iast"] == ["ikṣvāku", "vaṃśa", "prabhavaḥ"]
     and r[0]["compound_type"] is None),
    ("compound-simple-verb", "identify_compound", {"word": "gacCati"},
     lambda r: r.startswith("No split found")),
    # resolve_ambiguity: what the shared Analyzer actually selected.
    ("resolve-gacchati-verb", "resolve_ambiguity", {"text": "रामो वनं गच्छति"},
     lambda r: _selected(r, "gacCati")["lemma"] == "gam"
     and _selected(r, "gacCati")["morphology"]["tense"] == "present"),
    ("resolve-index-in-forest", "resolve_ambiguity", {"text": "रामो वनं गच्छति"},
     lambda r: 0 <= r["selected_parse_index"] < r["total_candidates"]),
]

# Rows that never reach vidyut: missing arguments must be rejected up front.
ERROR_CASES: list[Case] = [
    (f"{tool}-requires-{key}", tool, {}, lambda r, key=key: r == f"Error: {key} parameter is required")
    for tool, key in [
        ("explain_parse", "text"),
        ("identify_compound", "word"),
        ("get_pratyaya", "word"),
        ("resolve_ambiguity", "text"),
    ]
]


async def check_cases(dispatch, cases: list[Case]) -> None:
    """Run every row and report all failures together."""
    failures: list[str] = []
    for case_id, tool, arguments, check in cases:
        result = await dispatch(tool, arguments)
        reply = _reply(result[0].text) if result else None
        try:
            ok = check(reply)
        except (StopIteration, KeyError, IndexError, TypeError, AttributeError) as exc:
            ok, reply = False, f"{reply!r} ({type(exc).__name__}: {exc})"
        if not ok:
            failures.append(f"{case_id}: {str(reply)[:300]}")
    assert not failures, "\n".join(failures)


class TestGrammarToolsRegistration:
    """Tests for grammar tools registration."""

    def test_build_exposes_expected_tools(self) -> None:
        """build_grammar_tools returns the four grammar tool specs."""
        tools, _dispatch = build_grammar_tools()
        names = {t.name for t in tools}
        assert names == {
            "explain_parse",
            "identify_compound",
            "get_pratyaya",
            "resolve_ambiguity",
        }

    @pytest.mark.asyncio
    async def test_dispatch_returns_none_for_unknown_tool(self, dispatch) -> None:
        """The dispatcher returns None for tools it does not own."""
        assert await dispatch("not_a_tool", {}) is None


class TestGrammarToolOutput:
    """The tools, called as a client would, against real vidyut output."""

    @pytest.mark.asyncio
    async def test_missing_arguments_rejected(self, dispatch) -> None:
        """Runs without the vidyut bundle, so it stays separate from CASES."""
        await check_cases(dispatch, ERROR_CASES)

    @pytest.mark.asyncio
    @needs_vidyut
    async def test_grammar_cases(self, dispatch) -> None:
        await check_cases(dispatch, CASES)
