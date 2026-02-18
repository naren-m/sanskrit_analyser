"""Configuration for training data generation."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrainingConfig:
    """Configuration for training data generation.

    Attributes:
        min_confidence: Minimum confidence threshold for including examples.
        max_examples: Maximum number of examples to generate (0 = unlimited).
        output_dir: Directory for output files.
        corpus_dir: Directory containing source corpora.
        grammar_output: Filename for grammar training data.
        disambig_output: Filename for disambiguation training data.
        batch_size: Number of sentences to process in each batch.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
    """

    min_confidence: float = 0.85
    max_examples: int = 0
    output_dir: Path = field(default_factory=lambda: Path("training_data"))
    corpus_dir: Path = field(default_factory=lambda: Path("sanskrit_analyzer/data/corpora"))
    grammar_output: str = "grammar_training.jsonl"
    disambig_output: str = "disambig_training.jsonl"
    batch_size: int = 100
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "TrainingConfig":
        """Create config from environment variables."""
        return cls(
            min_confidence=float(os.getenv("TRAIN_MIN_CONFIDENCE", "0.85")),
            max_examples=int(os.getenv("TRAIN_MAX_EXAMPLES", "0")),
            output_dir=Path(os.getenv("TRAIN_OUTPUT_DIR", "training_data")),
            corpus_dir=Path(os.getenv("TRAIN_CORPUS_DIR", "sanskrit_analyzer/data/corpora")),
            batch_size=int(os.getenv("TRAIN_BATCH_SIZE", "100")),
            log_level=os.getenv("TRAIN_LOG_LEVEL", "INFO"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingConfig":
        """Create config from dictionary."""
        return cls(
            min_confidence=float(data["min_confidence"]) if "min_confidence" in data else 0.85,
            max_examples=int(data["max_examples"]) if "max_examples" in data else 0,
            output_dir=Path(data["output_dir"]) if "output_dir" in data else Path("training_data"),
            corpus_dir=Path(data["corpus_dir"]) if "corpus_dir" in data else Path("sanskrit_analyzer/data/corpora"),
            grammar_output=str(data["grammar_output"]) if "grammar_output" in data else "grammar_training.jsonl",
            disambig_output=str(data["disambig_output"]) if "disambig_output" in data else "disambig_training.jsonl",
            batch_size=int(data["batch_size"]) if "batch_size" in data else 100,
            log_level=str(data["log_level"]) if "log_level" in data else "INFO",
        )

    def grammar_output_path(self) -> Path:
        """Get full path for grammar training data output."""
        return self.output_dir / self.grammar_output

    def disambig_output_path(self) -> Path:
        """Get full path for disambiguation training data output."""
        return self.output_dir / self.disambig_output
