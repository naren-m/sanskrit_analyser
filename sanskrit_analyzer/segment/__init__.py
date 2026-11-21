"""Lexicon-anchored sandhi segmentation (tier 1, no neural rescoring).

Public surface:

* :class:`~sanskrit_analyzer.segment.lexicon_segmenter.LexiconSegmenter` —
  k-best segmentation DP over a caller-supplied word-frequency lexicon.
* :func:`~sanskrit_analyzer.segment.lexicon_segmenter.pausa` — utterance-final
  form of a pada.
"""

from sanskrit_analyzer.segment.lexicon_segmenter import LexiconSegmenter, pausa

__all__ = ["LexiconSegmenter", "pausa"]
