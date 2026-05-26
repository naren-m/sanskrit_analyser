"""Tests for TrainingHistory."""

import pytest

from sanskrit_analyzer.embeddings.training.history import TrainingHistory


class TestTrainingHistory:
    def test_empty_history(self):
        h = TrainingHistory()
        assert h.epochs == []
        assert h.train_loss == []
        assert h.val_loss == []

    def test_record_epoch_appends(self):
        h = TrainingHistory()
        h.record(epoch=0, train_loss=2.5, val_loss=2.7)
        h.record(epoch=1, train_loss=1.8, val_loss=2.1)
        assert h.epochs == [0, 1]
        assert h.train_loss == [2.5, 1.8]
        assert h.val_loss == [2.7, 2.1]

    def test_val_loss_optional(self):
        h = TrainingHistory()
        h.record(epoch=0, train_loss=1.0)
        assert h.val_loss == [None]

    def test_to_dict_serializable(self):
        h = TrainingHistory()
        h.record(epoch=0, train_loss=1.5, val_loss=1.8)
        d = h.to_dict()
        assert d == {
            "epochs": [0],
            "train_loss": [1.5],
            "val_loss": [1.8],
        }
