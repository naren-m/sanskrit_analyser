"""The non-slow tier must fail loudly on anything that loads model weights."""

import pytest

from conftest import GUARDED_ENTRY_POINTS, _resolve


@pytest.mark.parametrize("module_name, attr_path", GUARDED_ENTRY_POINTS)
def test_guard_blocks_weight_loading(module_name, attr_path):
    resolved = _resolve(module_name, attr_path)
    if resolved is None:
        pytest.skip(f"{module_name}.{attr_path} not importable here")
    owner, name = resolved
    with pytest.raises(RuntimeError, match="mark the test|Mark the test") as exc:
        getattr(owner, name)("some/model")
    assert "slow" in str(exc.value)
    assert "test_guard_blocks_weight_loading" in str(exc.value)
