"""Tests for TrainingHistory."""

from sanskrit_analyzer.embeddings.training.history import TrainingHistory


def test_record_and_serialize():
    h = TrainingHistory()
    assert h.to_dict() == {"epochs": [], "train_loss": [], "val_loss": []}

    h.record(epoch=0, train_loss=2.5, val_loss=2.7)
    h.record(epoch=1, train_loss=1.8, val_loss=2.1)
    # val_loss is optional and recorded as None.
    h.record(epoch=2, train_loss=1.0)

    assert h.epochs == [0, 1, 2]
    assert h.train_loss == [2.5, 1.8, 1.0]
    assert h.val_loss == [2.7, 2.1, None]
    assert h.to_dict() == {
        "epochs": [0, 1, 2],
        "train_loss": [2.5, 1.8, 1.0],
        "val_loss": [2.7, 2.1, None],
    }
