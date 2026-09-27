import pytest

from sanskrit_analyzer.validation.kosha_vocabulary import KoshaVocabulary
from tests._cases import check_cases


@pytest.fixture(scope="module")
def vocab():
    try:
        return KoshaVocabulary()
    except Exception:
        pytest.skip("vidyut kosha data not available")


# (id, method, SLP1 word, expected result; "stem" means any non-None stem)
LOOKUP_CASES = [
    ("contains-root-gam", "contains", "gam", True),
    ("contains-stem-vana", "contains", "vana", True),
    ("rejects-nonword", "contains", "xyzzqq", False),
    ("finds-stem-for-inflected-gacCati", "find_stem", "gacCati", "stem"),
    # indeclinables delegate to the curated vocabulary
    ("avyaya-ca-delegates-to-curated", "is_indeclinable", "ca", True),
]


def test_lookup(vocab):
    def check(method, word, expected):
        got = getattr(vocab, method)(word)
        if expected == "stem":
            assert got is not None
        else:
            assert bool(got) is expected

    check_cases(LOOKUP_CASES, check)
