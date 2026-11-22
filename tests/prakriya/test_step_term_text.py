"""step_term_text accepts a 0.4.0 str and a fork Term (text, was_changed)."""
from types import SimpleNamespace

import pytest

from sanskrit_analyzer.prakriya.analyzer import step_term_text


def _term(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, was_changed=False)


class _Bare:
    def __str__(self) -> str:
        return "bare"


@pytest.mark.parametrize(
    ("result", "want"),
    [
        (["Bav", "a", "ti"], "Bav + a + ti"),
        ([_term("Bav"), _term("a"), _term("ti")], "Bav + a + ti"),
        (["Bav", _term("a"), "ti"], "Bav + a + ti"),
        ([_Bare()], "bare"),
    ],
)
def test_step_term_text_joins(result, want) -> None:
    assert " + ".join(step_term_text(t) for t in result) == want
