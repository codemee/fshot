import pytest

from fshot.settings import virtual_repaint_seconds


@pytest.mark.parametrize("value, expected", [
    (0, 0), (0.4, 0.4), ("1.5", 1.5), (-1, 0), (100, 10),
    (None, 1.5), ("invalid", 1.5), (float("nan"), 1.5), (float("inf"), 1.5),
])
def test_virtual_repaint_wait_bounds_and_invalid_saved_values(value, expected):
    assert virtual_repaint_seconds(value) == expected
