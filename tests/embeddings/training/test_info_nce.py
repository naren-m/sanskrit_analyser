"""Tests for info_nce_loss."""

import math

import torch

from sanskrit_analyzer.embeddings.training.info_nce import info_nce_loss
from tests._cases import check_cases


def _random_pairs() -> float:
    # With random vectors, softmax over N candidates ~ uniform 1/N, so loss ~ ln(N).
    torch.manual_seed(0)
    a = torch.nn.functional.normalize(torch.randn(8, 16), dim=1)
    b = torch.nn.functional.normalize(torch.randn(8, 16), dim=1)
    return info_nce_loss(a, b, torch.ones(8, dtype=torch.int64), temperature=1.0).item()


def _label_zero_delta() -> float:
    with_zero = info_nce_loss(torch.eye(3), torch.eye(3), torch.tensor([1, 1, 0]), temperature=0.05)
    without = info_nce_loss(
        torch.eye(3)[:2], torch.eye(3)[:2], torch.tensor([1, 1]), temperature=0.05
    )
    return abs(with_zero.item() - without.item())


# (id, loss probe, predicate on the value)
CASES = [
    (
        # a_i == b_i and orthogonal across the batch: the diagonal dominates softmax.
        "perfect alignment gives near-zero loss",
        lambda: info_nce_loss(
            torch.eye(4), torch.eye(4), torch.tensor([1, 1, 1, 1]), temperature=0.05
        ).item(),
        lambda v: v < 0.01,
    ),
    ("random alignment gives loss near ln(N)", _random_pairs, lambda v: abs(v - math.log(8)) < 1.0),
    ("label-0 pairs are dropped before the loss", _label_zero_delta, lambda v: v < 1e-5),
    (
        # Need >=2 positives for in-batch negatives to exist.
        "fewer than two positives gives zero",
        lambda: info_nce_loss(
            torch.eye(2), torch.eye(2), torch.tensor([1, 0]), temperature=0.05
        ).item(),
        lambda v: v == 0.0,
    ),
]


def test_info_nce_loss():
    def check(probe, ok):
        value = probe()
        assert ok(value), value

    check_cases(CASES, check)

    a = torch.eye(3, requires_grad=True)
    b = torch.eye(3, requires_grad=True)
    info_nce_loss(a, b, torch.tensor([1, 1, 1]), temperature=0.05).backward()
    assert a.grad is not None
    assert b.grad is not None
