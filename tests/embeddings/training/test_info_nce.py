"""Tests for info_nce_loss."""

import math

import pytest
import torch

from sanskrit_analyzer.embeddings.training.info_nce import info_nce_loss


class TestInfoNCELoss:
    def test_perfect_alignment_gives_minimum_loss(self):
        # When a_i == b_i exactly and orthogonal across the batch,
        # the diagonal dominates softmax and loss approaches 0.
        a = torch.eye(4)
        b = torch.eye(4)
        labels = torch.tensor([1, 1, 1, 1])
        loss = info_nce_loss(a, b, labels, temperature=0.05)
        assert loss.item() < 0.01

    def test_random_alignment_gives_loss_near_log_n(self):
        # With random vectors, softmax over N candidates ~ uniform 1/N,
        # so loss ~ ln(N).
        torch.manual_seed(0)
        a = torch.randn(8, 16)
        a = torch.nn.functional.normalize(a, dim=1)
        b = torch.randn(8, 16)
        b = torch.nn.functional.normalize(b, dim=1)
        labels = torch.ones(8, dtype=torch.int64)
        loss = info_nce_loss(a, b, labels, temperature=1.0)
        assert abs(loss.item() - math.log(8)) < 1.0

    def test_label_zero_pairs_excluded(self):
        a = torch.eye(3)
        b = torch.eye(3)
        labels = torch.tensor([1, 1, 0])
        loss_with_zero = info_nce_loss(a, b, labels, temperature=0.05)

        a2 = torch.eye(3)[:2]
        b2 = torch.eye(3)[:2]
        labels2 = torch.tensor([1, 1])
        loss_without = info_nce_loss(a2, b2, labels2, temperature=0.05)
        torch.testing.assert_close(loss_with_zero, loss_without, rtol=1e-5, atol=1e-5)

    def test_too_few_positives_returns_zero(self):
        # Need >=2 positives for in-batch negatives to exist.
        a = torch.eye(2)
        b = torch.eye(2)
        labels = torch.tensor([1, 0])
        loss = info_nce_loss(a, b, labels, temperature=0.05)
        assert loss.item() == 0.0

    def test_zero_temperature_raises(self):
        a = torch.eye(3)
        b = torch.eye(3)
        labels = torch.tensor([1, 1, 1])
        with pytest.raises(ValueError, match="temperature must be > 0"):
            info_nce_loss(a, b, labels, temperature=0.0)

    def test_negative_temperature_raises(self):
        a = torch.eye(3)
        b = torch.eye(3)
        labels = torch.tensor([1, 1, 1])
        with pytest.raises(ValueError, match="temperature must be > 0"):
            info_nce_loss(a, b, labels, temperature=-0.1)

    def test_loss_is_differentiable(self):
        a = torch.eye(3, requires_grad=True)
        b = torch.eye(3, requires_grad=True)
        labels = torch.tensor([1, 1, 1])
        loss = info_nce_loss(a, b, labels, temperature=0.05)
        loss.backward()
        assert a.grad is not None
        assert b.grad is not None
