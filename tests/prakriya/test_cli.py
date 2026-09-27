"""CLI smoke tests (capsys, no subprocess)."""
import json

import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.__main__ import main
from tests._cases import check_cases


def _json_top_lemma_bu(out: str) -> None:
    rec = json.loads(out)
    assert rec["padas"][0]["analyses"][0]["lemma"] == "BU"


def _human_shows_sutra_codes(out: str) -> None:
    assert "7.3.84" in out and "BU" in out


# (id, argv, exit code, check on stdout or None)
CLI_CASES = [
    ("json-output", ["--json", "भवति"], 0, _json_top_lemma_bu),
    ("human-output-shows-sutra-codes", ["Bavati"], 0, _human_shows_sutra_codes),
    ("no-args-is-error", [], 2, None),
]


def test_cli(capsys):
    def check(argv, code, expect):
        capsys.readouterr()
        assert main(argv) == code
        if expect is not None:
            expect(capsys.readouterr().out)

    check_cases(CLI_CASES, check)
