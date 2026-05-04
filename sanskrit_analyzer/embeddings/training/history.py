"""Per-epoch training-loss record for the projection-head trainer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrainingHistory:
    """Append-only record of epoch losses, dumpable to JSON."""

    epochs: list[int] = field(default_factory=list)
    train_loss: list[float] = field(default_factory=list)
    val_loss: list[Optional[float]] = field(default_factory=list)

    def record(
        self, epoch: int, train_loss: float, val_loss: Optional[float] = None
    ) -> None:
        self.epochs.append(epoch)
        self.train_loss.append(float(train_loss))
        self.val_loss.append(float(val_loss) if val_loss is not None else None)

    def to_dict(self) -> dict:
        return {
            "epochs": list(self.epochs),
            "train_loss": list(self.train_loss),
            "val_loss": list(self.val_loss),
        }
