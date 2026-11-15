"""Citation roots for display: Dhātupāṭha upadeśa -> the root a learner knows."""
from __future__ import annotations

import pytest

from sanskrit_analyzer.reader.derive import citation_root


@pytest.mark.parametrize(
    ("upadesa", "want"),
    [
        ("Bu\\jo~", "Buj"), ("janI~\\", "jan"), ("mf\\N", "mf"), ("asa~", "as"),
        ("RI\\Y", "nI"),         # 6.1.65 Ro naH: initial R -> n
        ("zWA\\", "sTA"),        # 6.1.64 DAtvAdeH zaH saH, with zW -> sT
        ("zwu\\Y", "stu"),
        ("df\\Si~r", "dfS"),     # ir-anubandha
        ("kapi~\\", "kamp"),     # idit: num augment (7.1.58)
        ("citi~", "cint"), ("vadi~\\", "vand"),
        ("pra\\Ca~", "pracC"),   # 6.1.73 che ca: tuk before C
        ("qukf\\Y", "kf"),
    ],
)
def test_citation_root(upadesa: str, want: str) -> None:
    assert citation_root(upadesa) == want
