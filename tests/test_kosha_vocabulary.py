import logging

import pytest

from sanskrit_analyzer.validation.kosha_vocabulary import KoshaVocabulary

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def vocab():
    try:
        return KoshaVocabulary()
    except Exception:
        logger.debug("KoshaVocabulary failed to load", exc_info=True)
        pytest.skip("vidyut kosha data not available")


def test_contains_known_lemma(vocab):
    assert vocab.contains("gam")
    assert vocab.contains("vana")
    assert not vocab.contains("xyzzqq")


def test_find_stem_for_inflected_form(vocab):
    assert vocab.find_stem("gacCati") is not None


def test_indeclinable_passthrough(vocab):
    assert isinstance(vocab.is_indeclinable("ca"), bool)
