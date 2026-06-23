"""Typed result model for the Deep Read facility.

These dataclasses are a *lossless typed view* over the legacy plain-dict shape
that downstream consumers (the ramayanam ``/deep-read`` page and the Rāmāyaṇa
gold eval) already depend on. The invariant that gates the whole promotion is::

    DeepReadResult.from_legacy(d).to_dict() == d

so :meth:`to_dict` reproduces the original dict field-for-field, including the
optional ``reason`` / ``error`` token keys and any forward-compatible extras.
Nothing here recomputes analysis; the orchestration in
:mod:`sanskrit_analyzer.deep_read.facade` builds the dict and wraps it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Keys we model explicitly; everything else round-trips through ``extra``.
_TOKEN_KNOWN = {"surface", "slp1", "resolved", "analyses", "reason", "error"}
_RESULT_KNOWN = {"input", "slp1", "engine", "tokens", "notes"}


@dataclass
class DhatuBlock:
    """A verbal root (dhātu) extracted from a pada analysis."""

    root: str
    root_dev: str | None = None
    gana: str | None = None
    gana_num: int | None = None
    artha_sa: str | None = None
    artha_iast: str | None = None
    english: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "root_dev": self.root_dev,
            "gana": self.gana,
            "gana_num": self.gana_num,
            "artha_sa": self.artha_sa,
            "artha_iast": self.artha_iast,
            "english": self.english,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DhatuBlock":
        return cls(
            root=d.get("root"),
            root_dev=d.get("root_dev"),
            gana=d.get("gana"),
            gana_num=d.get("gana_num"),
            artha_sa=d.get("artha_sa"),
            artha_iast=d.get("artha_iast"),
            english=d.get("english"),
        )


@dataclass
class Analysis:
    """One candidate analysis of a single pada."""

    kind: str  # verb | derived | nominal | indeclinable | unknown
    lemma: str | None = None
    dhatu: DhatuBlock | None = None
    morphology: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "lemma": self.lemma,
            "dhatu": self.dhatu.to_dict() if self.dhatu else None,
            "morphology": self.morphology,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Analysis":
        dhatu = d.get("dhatu")
        return cls(
            kind=d.get("kind", "unknown"),
            lemma=d.get("lemma"),
            dhatu=DhatuBlock.from_dict(dhatu) if dhatu else None,
            morphology=dict(d.get("morphology") or {}),
        )


@dataclass
class Token:
    """One pada with its candidate analyses."""

    surface: str | None = None
    slp1: str | None = None
    resolved: bool = False
    analyses: list[Analysis] = field(default_factory=list)
    reason: str | None = None  # why an unresolved token did not resolve
    error: str | None = None  # internal failure note (transliteration/kosha)
    extra: dict[str, Any] = field(default_factory=dict)  # forward-compat keys

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "surface": self.surface,
            "slp1": self.slp1,
            "resolved": self.resolved,
            "analyses": [a.to_dict() for a in self.analyses],
        }
        # ``reason``/``error`` are present in the legacy dict only when set.
        if self.reason is not None:
            out["reason"] = self.reason
        if self.error is not None:
            out["error"] = self.error
        out.update(self.extra)
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Token":
        return cls(
            surface=d.get("surface"),
            slp1=d.get("slp1"),
            resolved=bool(d.get("resolved", False)),
            analyses=[Analysis.from_dict(a) for a in (d.get("analyses") or [])],
            reason=d.get("reason"),
            error=d.get("error"),
            extra={k: v for k, v in d.items() if k not in _TOKEN_KNOWN},
        )


@dataclass
class DeepReadResult:
    """A full Deep Read analysis of one line: tokens with candidate dhātus."""

    input: str
    slp1: str | None = None
    engine: str = ""
    tokens: list[Token] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)  # forward-compat keys

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "input": self.input,
            "slp1": self.slp1,
            "engine": self.engine,
            "tokens": [t.to_dict() for t in self.tokens],
            "notes": list(self.notes),
        }
        out.update(self.extra)
        return out

    @classmethod
    def from_legacy(cls, d: dict[str, Any]) -> "DeepReadResult":
        """Wrap a legacy Deep Read result dict into the typed model losslessly."""
        return cls(
            input=d.get("input", ""),
            slp1=d.get("slp1"),
            engine=d.get("engine", ""),
            tokens=[Token.from_dict(t) for t in (d.get("tokens") or [])],
            notes=list(d.get("notes") or []),
            extra={k: v for k, v in d.items() if k not in _RESULT_KNOWN},
        )
