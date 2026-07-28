"""CLI smoke tests (capsys, no subprocess)."""
import json

import pytest

vidyut = pytest.importorskip("vidyut")

from sanskrit_analyzer.deep_read.kosha_engine import resolve_data_dir

pytestmark = pytest.mark.skipif(
    resolve_data_dir() is None, reason="vidyut data bundle not installed"
)

from sanskrit_analyzer.prakriya.__main__ import main


def test_json_output(capsys):
    assert main(["--json", "भवति"]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["padas"][0]["analyses"][0]["lemma"] == "BU"


def test_human_output_shows_sutra_codes(capsys):
    assert main(["Bavati"]) == 0
    out = capsys.readouterr().out
    assert "7.3.84" in out and "BU" in out


def test_no_args_is_error(capsys):
    assert main([]) == 2
