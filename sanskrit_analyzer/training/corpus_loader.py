"""Corpus loading utilities for Sanskrit text data."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class VerseMetadata:
    """Metadata for a verse or sentence from a corpus.

    Attributes:
        corpus: Name of the source corpus.
        chapter: Chapter or section number.
        verse: Verse or line number within the chapter.
        source_file: Path to the source file.
    """

    corpus: str
    chapter: str
    verse: int
    source_file: str


@dataclass
class CorpusEntry:
    """A single entry from a corpus with text and metadata.

    Attributes:
        text: The Sanskrit text content.
        metadata: Source metadata for the entry.
    """

    text: str
    metadata: VerseMetadata


class CorpusLoader:
    """Load Sanskrit text corpora from various file formats.

    Supports loading from:
    - Plain text files (.txt) with one sentence/verse per line
    - JSON files with structured verse data

    Example usage:
        loader = CorpusLoader(Path("corpora/ramayana.txt"), corpus_name="Ramayana")
        for entry in loader:
            print(entry.text, entry.metadata)
    """

    def __init__(
        self,
        path: Path,
        corpus_name: str | None = None,
        chapter: str = "1",
    ) -> None:
        """Initialize the corpus loader.

        Args:
            path: Path to the corpus file.
            corpus_name: Name of the corpus (defaults to filename).
            chapter: Default chapter/section identifier.
        """
        self.path = path
        self.corpus_name = corpus_name or path.stem
        self.chapter = chapter
        self._entries: list[CorpusEntry] = []
        self._loaded = False

    def _load_text_file(self) -> None:
        """Load entries from a plain text file (one per line)."""
        with open(self.path, encoding="utf-8") as f:
            verse_num = 0
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                verse_num += 1
                metadata = VerseMetadata(
                    corpus=self.corpus_name,
                    chapter=self.chapter,
                    verse=verse_num,
                    source_file=str(self.path),
                )
                self._entries.append(CorpusEntry(text=line, metadata=metadata))

    def _load_json_file(self) -> None:
        """Load entries from a JSON file with verse structure."""
        import json

        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)

        # Support various JSON structures
        if isinstance(data, list):
            # Simple list of verses
            for i, item in enumerate(data):
                if isinstance(item, str):
                    text = item
                    chapter = self.chapter
                elif isinstance(item, dict):
                    text = str(item.get("text") or item.get("verse") or "")
                    chapter = str(item.get("chapter") or self.chapter)
                else:
                    continue

                metadata = VerseMetadata(
                    corpus=self.corpus_name,
                    chapter=chapter,
                    verse=i + 1,
                    source_file=str(self.path),
                )
                self._entries.append(CorpusEntry(text=text, metadata=metadata))

        elif isinstance(data, dict):
            # Structured with chapters
            verses_data = data.get("verses", data.get("entries", []))
            verses: list[str | dict[str, str]] = verses_data if verses_data else []
            corpus_name = str(data.get("corpus", self.corpus_name))
            for i, item in enumerate(verses):
                if isinstance(item, str):
                    text = item
                    chapter = self.chapter
                elif isinstance(item, dict):
                    text = str(item.get("text") or item.get("verse") or "")
                    chapter = str(item.get("chapter") or self.chapter)
                else:
                    continue

                metadata = VerseMetadata(
                    corpus=corpus_name,
                    chapter=chapter,
                    verse=i + 1,
                    source_file=str(self.path),
                )
                self._entries.append(CorpusEntry(text=text, metadata=metadata))

    def load(self) -> None:
        """Load the corpus file into memory."""
        if self._loaded:
            return

        if not self.path.exists():
            raise FileNotFoundError(f"Corpus file not found: {self.path}")

        suffix = self.path.suffix.lower()
        if suffix == ".json":
            self._load_json_file()
        else:
            # Default to text file handling
            self._load_text_file()

        self._loaded = True

    def __iter__(self) -> Iterator[CorpusEntry]:
        """Iterate over corpus entries."""
        if not self._loaded:
            self.load()
        return iter(self._entries)

    def __len__(self) -> int:
        """Return number of entries in the corpus."""
        if not self._loaded:
            self.load()
        return len(self._entries)

    @property
    def entries(self) -> list[CorpusEntry]:
        """Get all corpus entries."""
        if not self._loaded:
            self.load()
        return self._entries
