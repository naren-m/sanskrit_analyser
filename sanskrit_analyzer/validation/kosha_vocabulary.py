"""Kosha-backed vocabulary for the split validator.

The curated :class:`Vocabulary` only knows ~99 lemmas (the Yoga Sutras
corpus), which causes :class:`SplitValidator` to penalise correct splits whose
real lemmas (e.g. ``gam``, ``vana``) are absent. This vocabulary instead backs
``contains`` / ``find_stem`` with the full ``vidyut.kosha`` (millions of forms),
so genuine Sanskrit words score positively and correct segmentations win.

It is duck-typed to match the interface :class:`SplitValidator` calls on its
vocabulary object: ``contains(lemma)``, ``is_indeclinable(text)``,
``find_stem(surface)`` (plus a ``words`` mapping used in ``_make_segment``).
Indeclinable detection is delegated to the curated :class:`Vocabulary`.
"""

from __future__ import annotations

import functools

from sanskrit_analyzer import vidyut_data
from sanskrit_analyzer.utils.desandhi import desandhi_candidates
from sanskrit_analyzer.validation.vocabulary import Vocabulary


class KoshaVocabulary:
    """Vocabulary backed by the full vidyut kosha.

    Implements the duck-typed interface the split validator relies on:
    ``contains``, ``is_indeclinable``, ``find_stem`` and a ``words`` mapping.
    """

    def __init__(self, data_path: str | None = None) -> None:
        """Initialize, opening the kosha and the curated indeclinable vocab.

        Args:
            data_path: Path to the vidyut kosha directory. Defaults to the
                shared process-wide kosha (see
                :func:`sanskrit_analyzer.vidyut_data.kosha`).

        Raises:
            Exception: If the kosha cannot be opened. The Analyzer wraps
                construction in try/except and falls back to the curated
                vocabulary, so a clear failure here is acceptable.
        """
        if data_path:
            from vidyut.kosha import Kosha

            self._kosha = Kosha(data_path)
        else:
            self._kosha = vidyut_data.kosha()

        # The curated vocabulary is consulted FIRST (it is purpose-tuned, e.g.
        # the Yoga-Sutra golden splits, and carries pos/lemma metadata); the
        # kosha only fills the long tail of real Sanskrit words the curated
        # list never had (e.g. ``gam``, ``vana``).
        self._curated = Vocabulary.load_default()

        # The validator reads ``vocab.words.get(...)`` for pos/lemma metadata
        # in ``_make_segment``; expose the curated mapping so curated words
        # keep their metadata. Kosha-only words simply yield ``{}`` (pos=None).
        self.words = self._curated.words

    # NOTE: lru_cache on a method keys on (self, form), so the cache is shared
    # across instances and keeps each instance alive for the process lifetime.
    # That is fine here — the Analyzer holds a single long-lived KoshaVocabulary.
    @functools.lru_cache(maxsize=100_000)
    def _kosha_has(self, form: str) -> bool:
        """Return True if *form* (already SLP1) yields a kosha entry."""
        try:
            return len(self._kosha.get(form)) > 0
        except Exception:
            return False

    def contains(self, slp1_lemma: str) -> bool:
        """Return True if the curated vocab or the kosha knows *slp1_lemma*."""
        if not slp1_lemma:
            return False
        if self._curated.contains(slp1_lemma):
            return True
        return any(self._kosha_has(form) for form in desandhi_candidates(slp1_lemma))

    def find_stem(self, slp1_form: str) -> str | None:
        """Return a known stem for *slp1_form*.

        The curated vocabulary is tried first (it maps inflected forms to
        their curated stem, e.g. for the Yoga-Sutra golden splits). Falling
        back to the kosha, return the surface form itself when it (or a
        de-sandhi variant) is a known kosha entry.
        """
        curated = self._curated.find_stem(slp1_form)
        if curated is not None:
            return curated
        if any(self._kosha_has(form) for form in desandhi_candidates(slp1_form)):
            return slp1_form
        return None

    def is_curated(self, text: str) -> bool:
        """Return True if *text* is known to the curated (not kosha) vocab.

        Used by the scorer as a tiebreaker: the curated list is hand-tuned
        (e.g. the Yoga-Sutra golden splits), so when several splits are equally
        "known", the one whose pieces come from the curated vocab should win
        over one that only resolves via the kosha's long tail of fragments.
        """
        if not text:
            return False
        return (
            self._curated.contains(text)
            or self._curated.find_stem(text) is not None
            or self._curated.is_indeclinable(text)
        )

    def is_indeclinable(self, slp1_lemma: str) -> bool:
        """Delegate indeclinable detection to the curated vocabulary."""
        return self._curated.is_indeclinable(slp1_lemma)

    def __len__(self) -> int:
        """Approximate size; the kosha is not flatly enumerable here."""
        return len(self._curated)
