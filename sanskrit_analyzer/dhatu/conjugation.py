"""Tiṅanta (conjugated verb) forms, derived on demand by ``vidyut.prakriya``.

Nothing is stored: the forms are generated from the Dhātupāṭha entry by the
same Pāṇinian engine that produces the sūtra traces, so every one of the
~2,200 roots can be conjugated in all ten lakāras rather than only the
handful a bundled table could hold.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import product
from typing import Any

from sanskrit_analyzer.models.scripts import Script
from sanskrit_analyzer.utils.transliterate import to_devanagari, to_iast
from sanskrit_analyzer.vidyut_data import VidyutUnavailable, resolve_data_dir

#: "lin" is ambiguous in traditional usage; treat the bare name as vidhi-liṅ.
_LAKARA_ALIASES = {"lin": "vidhilin", "lrng": "lrn"}

#: Lakāras accepted by the API/MCP surface, in traditional order, mapped to
#: the name of the matching ``vidyut.prakriya.Lakara`` member.
_VIDYUT_LAKARA = {
    "lat": "Lat",
    "lit": "Lit",
    "lut": "Lut",
    "lrt": "Lrt",
    "let": "Let",
    "lot": "Lot",
    "lan": "Lan",
    "vidhilin": "VidhiLin",
    "ashirlin": "AshirLin",
    "lun": "Lun",
    "lrn": "Lrn",
}

LAKARA_NAMES: tuple[str, ...] = tuple(_VIDYUT_LAKARA)

_PURUSHA_ORDER = (("prathama", "Prathama"), ("madhyama", "Madhyama"), ("uttama", "Uttama"))
_VACANA_ORDER = (("eka", "Eka"), ("dvi", "Dvi"), ("bahu", "Bahu"))
_PADA_ORDER = (("parasmaipada", "Parasmaipada"), ("ātmanepada", "Atmanepada"))


def is_available() -> bool:
    """True if the vidyut bundle needed for derivation is present."""
    return resolve_data_dir() is not None


def normalize_lakara(name: str | None) -> str | None:
    """Map a caller-supplied lakāra name to a canonical one, or None."""
    if not name:
        return None
    key = name.strip().lower()
    key = _LAKARA_ALIASES.get(key, key)
    return key if key in _VIDYUT_LAKARA else None


@lru_cache(maxsize=1)
def _entries_by_code() -> dict[str, Any]:
    data_dir = resolve_data_dir()
    if data_dir is None:
        raise VidyutUnavailable("vidyut data bundle not found; cannot derive forms")
    from vidyut.prakriya import Data

    return {e.code: e for e in Data(str(data_dir / "prakriya")).load_dhatu_entries()}


def conjugate(code: str, lakara: str = "lat") -> list[dict[str, Any]]:
    """Derive the tiṅanta paradigm for one Dhātupāṭha entry.

    Args:
        code: Dhātupāṭha code, e.g. ``"01.1137"`` for √gam.
        lakara: Lakāra name; see :data:`LAKARA_NAMES`.

    Returns:
        One entry per (pada, puruṣa, vacana) slot that the root actually
        forms. A root that is parasmaipada-only simply yields no ātmanepada
        rows, which is how the pada of a root is reported.

    Raises:
        VidyutUnavailable: the data bundle is missing.
        KeyError: the code is not in the Dhātupāṭha, or the lakāra is unknown.
    """
    canonical = normalize_lakara(lakara)
    if canonical is None:
        raise KeyError(f"unknown lakara: {lakara}")

    entry = _entries_by_code().get(code)
    if entry is None:
        raise KeyError(f"unknown dhatupatha code: {code}")

    from vidyut.prakriya import DhatuPada, Lakara, Pada, Prayoga, Purusha, Vacana, Vyakarana

    engine = Vyakarana()
    lakara_value = getattr(Lakara, _VIDYUT_LAKARA[canonical])
    forms: list[dict[str, Any]] = []
    slots = product(_PADA_ORDER, _PURUSHA_ORDER, _VACANA_ORDER)
    for (pada, pada_attr), (purusha, purusha_attr), (vacana, vacana_attr) in slots:
        derived = engine.derive(
            Pada.Tinanta(
                dhatu=entry.dhatu,
                prayoga=Prayoga.Kartari,
                lakara=lakara_value,
                purusha=getattr(Purusha, purusha_attr),
                vacana=getattr(Vacana, vacana_attr),
                dhatu_pada=getattr(DhatuPada, pada_attr),
            )
        )
        texts = sorted({p.text for p in derived})
        if texts:
            forms.append(
                {
                    "lakara": canonical,
                    "pada": pada,
                    "purusha": purusha,
                    "vacana": vacana,
                    "forms_slp1": texts,
                    "forms_devanagari": [to_devanagari(t, Script.SLP1) for t in texts],
                    "forms_iast": [to_iast(t, Script.SLP1) for t in texts],
                }
            )
    return forms


def padas_for(code: str) -> list[str]:
    """Which padas the root actually forms, derived rather than tabulated."""
    try:
        rows = conjugate(code, "lat")
    except (VidyutUnavailable, KeyError):
        return []
    return sorted({row["pada"] for row in rows})
