import pytest

from sanskrit_analyzer.validation.kosha_vocabulary import KoshaVocabulary


@pytest.fixture(scope="module")
def vocab():
    return KoshaVocabulary()


def test_contains_known_lemma(vocab):
    assert vocab.contains("gam")
    assert vocab.contains("vana")
    assert not vocab.contains("xyzzqq")


def test_find_stem_for_inflected_form(vocab):
    assert vocab.find_stem("gacCati") is not None


def test_indeclinable_passthrough(vocab):
    assert isinstance(vocab.is_indeclinable("ca"), bool)
