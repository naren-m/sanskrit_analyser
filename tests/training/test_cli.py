"""Tests for the training CLI."""

import argparse
import json
from pathlib import Path

from sanskrit_analyzer.training import cli


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class TestCoerceConfidence:
    """Tests for the _coerce_confidence helper."""

    def test_numeric_values_pass_through(self) -> None:
        assert cli._coerce_confidence(0.9) == 0.9
        assert cli._coerce_confidence(1) == 1.0

    def test_none_and_non_numeric_are_skipped(self) -> None:
        assert cli._coerce_confidence(None) is None
        assert cli._coerce_confidence("not-a-number") is None
        assert cli._coerce_confidence(True) is None

    def test_numeric_string_is_coerced(self) -> None:
        assert cli._coerce_confidence("0.75") == 0.75


class TestStatsCommand:
    """Tests for the stats command's confidence averaging."""

    def test_average_ignores_missing_and_null_confidence(
        self, tmp_path: Path, capsys
    ) -> None:
        """Average is computed only over examples with numeric confidence."""
        input_path = tmp_path / "data.jsonl"
        _write_jsonl(
            input_path,
            [
                {"metadata": {"confidence": 0.8}, "output": {}},
                {"metadata": {"confidence": 1.0}, "output": {}},
                # These must NOT drag the average toward 0.0:
                {"metadata": {"confidence": None}, "output": {}},
                {"metadata": {}, "output": {}},
            ],
        )

        args = argparse.Namespace(
            input=str(input_path), json=True, log_level="ERROR"
        )
        rc = cli.cmd_stats(args)
        assert rc == 0

        stats = json.loads(capsys.readouterr().out)
        assert stats["total_examples"] == 4
        # Average over the two valid values only: (0.8 + 1.0) / 2 = 0.9
        assert stats["average_confidence"] == 0.9

    def test_null_confidence_does_not_crash(self, tmp_path: Path, capsys) -> None:
        """A null confidence must not raise TypeError."""
        input_path = tmp_path / "data.jsonl"
        _write_jsonl(input_path, [{"metadata": {"confidence": None}, "output": {}}])

        args = argparse.Namespace(
            input=str(input_path), json=True, log_level="ERROR"
        )
        assert cli.cmd_stats(args) == 0
        stats = json.loads(capsys.readouterr().out)
        assert stats["average_confidence"] == 0.0
