"""D7 rule: boundary rows of the test strategy plus an integer oracle (FR-1.16)."""
import dataclasses

import pytest

from app.services.consistency import ConsistencyResult


def label(n: int, d: int) -> str:
    return ConsistencyResult.evaluate(n, d).label()


@pytest.mark.parametrize("n, anomaly, consistent", [
    (45, [37, 51], [38, 50]),
    (10, [2, 15], [3, 14]),
    (0, [5], [0, 4]),
    (1, [6], [0, 5]),
    (8, [0, 13], [1, 12]),
    (40, [32, 45], [33, 44]),
    (41, [33, 47], [34, 46]),
    (46, [38, 52], [39, 51]),
    (47, [38, 53], [39, 52]),
    (60, [50, 67], [51, 66]),
])
def test_boundaries(n, anomaly, consistent):
    assert [label(n, d) for d in anomaly] == ["anomaly"] * len(anomaly)
    assert [label(n, d) for d in consistent] == ["consistent"] * len(consistent)


def test_bounds_for_45():
    result = ConsistencyResult.evaluate(45, 40)
    assert (result.lower, result.upper, result.consistent) == (38, 50, True)


def test_integer_oracle():
    for n in range(0, 201):
        lower = n - max(7, -(-15 * n // 100))
        upper = n + max(4, -(-10 * n // 100))
        for d in range(0, n + 31):
            assert ConsistencyResult.evaluate(n, d).consistent == (lower <= d <= upper), (n, d)


def test_result_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        ConsistencyResult.evaluate(10, 10).d = 3
