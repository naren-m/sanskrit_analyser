"""Resolve the verbal root (dhātu) behind any Sanskrit word.

The ensemble engines give a *lemma* — for a verb that is already the root
(gacchati -> gam), but for a derived nominal it is only the stem (yoga, not
yuj). This module recovers the root for derived nominals too, which is the
educationally interesting fact ("yoga comes from √yuj, 'to yoke'").

Source of truth is vidyut's Kośa: its entries for derived stems are
``Kṛdanta`` pratipādikas that carry the originating ``DhatuEntry`` — the
root's aupadeśika form, its prefixes, gaṇa, and Sanskrit gloss (artha).
The raw aupadeśika still carries Pāṇinian it-markers (yu\\ja~ , ru\\Di~^r),
so we clean it via this package's own ``strip_anubandhas`` and prefer the
294-entry hand-curated ``core_root`` table when the root is in it
("neural/statistical proposes, Pāṇini disposes").

Two things the Kośa does not do for us:

* It files most upasarga-prefixed stems as *Basic* pratipādikas with no
  dhātu link at all, even where the bare derivative beside them is a
  Kṛdanta that has one (anuśāsana: Basic; śāsana: Kṛdanta -> √śās). So a
  canonical prefix gets peeled and the remainder resolved.
* Where a stem has several readings it gives no ranking, and taking the
  first yielded confident nonsense (vidyā from vi+√dā 'give'). So the
  readings are scored — see ``_best_candidate``. Callers that can reach the
  dictionary should pass ``preferred_root``: MW's own etymology outranks
  every heuristic here.

Everything is best-effort: if the vidyut data bundle is absent, resolve()
simply returns None and the caller keeps its prior behaviour.
"""
from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from typing import Any

from sanskrit_analyzer.dhatu.dhatupatha import DhatuKosha, strip_anubandhas

logger = logging.getLogger(__name__)


class DhatuResolver:
    """Lazy, process-wide resolver of stem/word -> root via vidyut Kośa."""

    def __init__(self) -> None:
        self._kosha: Any = None
        self._dhatu_kosha: DhatuKosha | None = None
        self._ready: bool | None = None

    def _ensure(self) -> bool:
        """Load the vidyut Kośa and the Dhātupāṭha index once; cache success."""
        if self._ready is not None:
            return self._ready
        try:
            from vidyut.kosha import Kosha

            from sanskrit_analyzer.prakriya.analyzer import resolve_data_dir

            data_dir = resolve_data_dir()
            if data_dir is None:
                raise RuntimeError("vidyut data bundle not found")
            self._kosha = Kosha(os.path.join(str(data_dir), "kosha"))
            self._dhatu_kosha = DhatuKosha()
            self._ready = True
        except Exception as e:  # missing data bundle
            logger.info("DhatuResolver unavailable: %s", e)
            self._ready = False
        return self._ready

    # Vidyut gaṇa str() form -> traditional dhātu class number (1..10).
    _GANA_NUM = {
        "BvAdi": 1, "adAdi": 2, "juhotyAdi": 3, "divAdi": 4, "svAdi": 5,
        "tudAdi": 6, "ruDAdi": 7, "tanAdi": 8, "kryAdi": 9, "curAdi": 10,
    }

    # Pronoun (sarvanāman) stems in SLP1 — closed class, no verbal root.
    # Backs up the is_avyaya check for stems the Kośa doesn't flag.
    _PRONOUN_STEMS = frozenset({
        "tad", "etad", "idam", "adas", "yad", "kim", "asmad", "yuzmad",
        "enad", "tyad", "eka", "sarva", "sva",
    })

    # Canonical upasargas in SLP1, plus the vowel-sandhi allomorphs they take
    # before a vowel-initial stem (prati + akṣa -> pratyakṣa). Value is the
    # underlying upasarga we report; key is what the written stem starts with.
    _UPASARGAS = {
        "prati": "prati", "praty": "prati", "pari": "pari", "pary": "pari",
        "aDi": "aDi", "aDy": "aDi", "anu": "anu", "anv": "anu",
        "aBi": "aBi", "aBy": "aBi", "ati": "ati", "aty": "ati",
        "upa": "upa", "upo": "upa", "ava": "ava", "apa": "apa", "api": "api",
        "nis": "nis", "nir": "nis", "niz": "nis", "dus": "dus", "dur": "dus",
        "sam": "sam", "saM": "sam", "parA": "parA", "pra": "pra",
        "ud": "ud", "ut": "ud", "ni": "ni", "ny": "ni", "vi": "vi", "vy": "vi",
        "su": "su", "A": "A",
    }

    # Privative (nañ) prefix — a negation, not an upasarga, so it is peeled to
    # reach the root but never reported among the dhātu's prefixes.
    _PRIVATIVES = ("an", "a")

    _RESIDUAL = re.compile(r"[iIuU]?~[\^a-zA-Z]*$")

    # Anubandhas that sit *before* the root in a Dhātupāṭha citation
    # (ñi, ṭu, ḍu, and the ovit marker o~): ñiṣvapa~ is √svap, ḍukṛñ is √kṛ,
    # ohāk is √hā. The o~ carries a tilde of its own, which is why it has to
    # come off before any trailing-residue rule looks at the string.
    _LEADING_IT = re.compile(r"^(?:Yi|wu|qu)*(?:o~)?")

    @classmethod
    def _normalize_citation(cls, root: str) -> str:
        """Undo the Dhātupāṭha's citation spelling to get the real root.

        The Dhātupāṭha cites roots in a conventional form: an initial s is
        written ṣ and an initial n is written ṇ (Pāṇini 6.1.64-65 read in
        reverse), so √sthā appears as ṣṭhā and √naś as ṇaś. Leaving that
        spelling in place showed readers roots that do not exist, and it also
        missed in both the Dhātupāṭha index and the dictionary.
        """
        root = cls._LEADING_IT.sub("", root)
        if root.startswith("z"):
            # ṣṭu (P. 8.4.41) retroflexed the whole cluster, so undoing the
            # citation's ṣ must de-retroflex what follows too: ṣṭhā -> sthā,
            # ṣṭabh -> stabh. Leaving it as sṭhā matches nothing anywhere.
            rest = root[1:]
            if rest:
                rest = cls._RETROFLEX_TO_DENTAL.get(rest[0], rest[0]) + rest[1:]
            root = "s" + rest
        elif root.startswith("R"):
            root = "n" + root[1:]
        return root

    _RETROFLEX_TO_DENTAL = {"w": "t", "W": "T", "q": "d", "Q": "D", "R": "n"}

    # A nasal before a palatal is ñ, not n: √sañj, √rañj. Purely how the root
    # is written, so it is applied after attestation — the Dhātupāṭha index
    # spells these with a plain n and would otherwise miss.
    _PALATAL_NASAL = re.compile(r"n([jc])")

    def _clean_root(self, aupadeshika: str) -> tuple[str, bool, bool]:
        """(clean SLP1 root, attested-in-dhatupatha, hand-curated)."""
        assert self._dhatu_kosha is not None
        stripped = strip_anubandhas(aupadeshika)
        # An it-marker standing *before* the root (o~hA, YizvapA~) has to come
        # off first: its tilde is indistinguishable from the tail the residue
        # rule below strips, so running that rule first eats the root and
        # leaves the marker vowel (o~hA -> 'o', losing √hā).
        lead = self._LEADING_IT.sub("", stripped)
        # strip_anubandhas leaves nasal-infix / retroflex residues like
        # 'rudhi~' or 'dfSi~r'; drop the linking vowel + nasal marker tail.
        cited = self._RESIDUAL.sub("", lead).rstrip("~^\\")
        root = self._normalize_citation(cited)
        # The index is keyed by neither spelling consistently: uncurated roots
        # keep their citation ṣ/ṇ (√sidh is filed as ṣidh — 90 of 97 such roots
        # are reachable only that way) and some keep the leading marker
        # (core_root o~vij). Try each key, then normalise whatever answers —
        # ṣidh and o~vij must never reach the reader.
        entries = None
        for key in (root, cited, stripped.rstrip("~^\\")):
            entries = self._dhatu_kosha.lookup(key)
            if entries:
                break
        if entries:
            best = next((e for e in entries if e.get("curated")), entries[0])
            attested = self._normalize_citation(best.get("core_root") or root)
            # The index reduces a few roots to a single consonant — it reads
            # the ghu- of ghuṇa/ghuṭa as an it-marker and files √ghuṇ under
            # 'ṇ'. Prefer our own cleaned form over a core_root that is not a
            # possible root; √n teaches the reader something that isn't so.
            if not self._is_plausible_root(attested):
                attested = root
            verified = self._is_plausible_root(attested)
            return (self._PALATAL_NASAL.sub(r"Y\1", attested), verified,
                    verified and bool(best.get("curated")))
        return self._PALATAL_NASAL.sub(r"Y\1", root), False, False

    @classmethod
    def _is_plausible_root(cls, root: str) -> bool:
        """No Sanskrit root is a bare consonant or a punctuation placeholder.

        One-letter roots do exist, but every one of them is a vowel (√i, √ṛ,
        √u), so a single consonant marks upstream damage rather than a root.
        """
        if not root or not root.isalpha():
            return False
        return len(root) > 1 or root in cls._VOWELS

    def resolve(
        self, *candidates_slp1: str, preferred_root: str | None = None
    ) -> dict[str, Any] | None:
        """Return root info for the candidate that best maps to a dhātu.

        Pass SLP1 forms most-specific-first (surface, then lemma). A finite
        verb is read from the surface; anything else prefers the lemma, so a
        word reads the same wherever it occurs. Returns a dict with SLP1 root
        fields the adapter transliterates for display, or None when nothing
        resolves (particles, pronouns, unknown stems).
        """
        if not self._ensure():
            return None
        cands = [(c or "").strip().lstrip("'") for c in candidates_slp1]
        cands = [c for c in cands if c]

        # Indeclinables and pronouns have no verbal root, yet the Kośa lists
        # obscure verb/nominal homographs for them (ca -> √ci) and for their
        # inflected forms (tasya -> √tas). Skip the whole word if *any*
        # candidate — surface OR lemma — is an avyaya or a pronoun stem, so an
        # inflected pronoun can't slip a spurious root past its flagged lemma.
        if self.is_rootless(*cands):
            return None

        # Candidates arrive most-specific-first (surface, then lemma). A
        # finite-verb reading of the surface settles the word outright — √gam
        # lives in gacchati, not in any stem. A *nominal* reading of an
        # inflected surface does not settle it, though: case endings were
        # picking readings of their own, so viṣayam matched a vi+√siv 'to sew'
        # krdanta while viṣayā matched √viṣ, giving one word three etymologies
        # across the text. So a nominal hit on the surface is held back and the
        # lemma is asked; the held reading is used only when the lemma yields
        # nothing *and* the root underlies the lemma anyway (see below).
        unique = list(dict.fromkeys(cands))
        readings: list[dict[str, Any] | None] = []
        for cand in unique:
            best = self._best_candidate(cand, preferred_root=preferred_root)
            if best and best.get("is_verb"):
                return best
            readings.append(best)
        # No finite verb: the last (most general) candidate that resolves wins,
        # and a reading found only under an inflected surface is discarded
        # rather than shown — that is the difference between viṣaya reading
        # √viṣ everywhere and reading √siv wherever it happens to be accusative.
        for best in reversed(readings[1:] or readings):
            if best:
                return best
        # Only the inflected surface resolved. That is trustworthy when the
        # root actually underlies the lemma — kliṣṭa gives √kliś and the lemma
        # kliś *is* that root, so every inflection would say the same thing.
        # It is not trustworthy when the root is a stranger to the lemma, and
        # that is the viṣayam/vi+√siv 'to sew' case: an accident of the case
        # ending, which would disagree with the word's other occurrences.
        first = readings[0]
        if first and (len(unique) == 1
                      or self._skeleton_fits(first["root_slp1"], unique[-1])):
            return first

        # The Kośa files many upasarga-prefixed stems as *Basic* pratipādikas
        # with no dhātu link, while the bare derivative beside them is a
        # Kṛdanta that has one (anuśāsana: Basic; śāsana: Kṛdanta -> √śās).
        # Peel a canonical prefix and resolve the remainder.
        for cand in cands:
            peeled = self._resolve_peeled(cand, preferred_root=preferred_root)
            if peeled:
                return peeled
        return None

    def is_rootless(self, *candidates_slp1: str) -> bool:
        """True for words that have no verbal root at all.

        Indeclinables and pronouns have none, yet the Kośa lists obscure
        verb/nominal homographs for them (ca -> √ci) and for their inflected
        forms (tasya -> √tas). One flagged candidate — surface OR lemma —
        disqualifies the word, so an inflected pronoun cannot slip a spurious
        root past its flagged lemma. Callers must consult this before falling
        back to any other root source.
        """
        if not self._ensure():
            return False
        cands = [c for c in ((c or "").strip().lstrip("'") for c in candidates_slp1) if c]
        if any(c in self._PRONOUN_STEMS for c in cands):
            return True
        return any(
            getattr(e, "is_avyaya", False)
            for cand in cands for e in self._kosha.get(cand)
        )

    def _iter_dhatu_entries(self, form: str) -> Iterator[tuple[Any, bool]]:
        """Yield (DhatuEntry, is_finite_verb) for every reading of ``form``."""
        for entry in self._kosha.get(form):
            is_verb = type(entry).__name__.endswith("Tinanta")
            # Both Tiṅanta (direct) and krdanta Subanta (via pratipadika)
            # carry the originating DhatuEntry.
            de = getattr(entry, "dhatu_entry", None)
            if de is None:
                pe = getattr(entry, "pratipadika_entry", None)
                de = getattr(pe, "dhatu_entry", None) if pe else None
            if de is not None:
                yield de, is_verb

    _VOWELS = set("aAiIuUfFxXeEoO")

    @classmethod
    def _skeleton(cls, form: str) -> str:
        """Consonant skeleton of a form — its vowel-grade-independent shape."""
        return "".join(c for c in form if c not in cls._VOWELS and c.isalpha())

    @classmethod
    def _initial_fits(cls, root: str, stem: str, prefixed: bool) -> bool:
        """An unprefixed derivative opens with its root's first consonant.

        Nothing derives ānanda from √ad 'to eat' — a root with no upasarga
        keeps its initial consonant at the front of the word it builds. Only
        checked for prefix-free readings, since an upasarga covers the front.
        """
        if prefixed:
            return True
        root_skel, stem_skel = cls._skeleton(root), cls._skeleton(stem)
        if not root_skel or not stem_skel:
            return False
        return root_skel[0] == stem_skel[0]

    @classmethod
    def _skeleton_fits(cls, root: str, stem: str) -> bool:
        """Could ``root``'s consonants be the ones showing up in ``stem``?

        Derivation changes vowel grade freely (kliś -> kleśa, vṛt -> vartana)
        but leaves the consonants in order, so comparing skeletons as a
        subsequence tolerates guṇa/vṛddhi while still rejecting a root that
        simply is not in the word (āgama is √gam, not √i).
        """
        root_skel, stem_skel = cls._skeleton(root), cls._skeleton(stem)
        if not root_skel:
            return False
        it = iter(stem_skel)
        return all(c in it for c in root_skel)

    def _best_candidate(self, form: str, krdanta_only: bool = False,
                        preferred_root: str | None = None) -> dict[str, Any] | None:
        """Pick the most plausible root among a stem's homographic readings.

        A stem such as vidyā has several Kṛdanta readings (vi+√dā 'give',
        vi+√do 'cut', √vid 'know'); taking whichever the Kośa lists first gave
        wrong roots on common words. Rank instead, strongest signal first:

        1. The root the dictionary itself names for this word, when the caller
           supplies one — MW's 'fr. √rañj' settles rāga, which the Kośa's own
           readings (√rāj, √rag, √rañj) cannot.
        2. A finite-verb reading, when present, *is* the intended reading of a
           finite form (gacchati -> √gam), so it outranks a homographic noun.
        3. A root whose consonants actually appear in the stem, in order.
        4. A prefix-free reading beats a prefixed one. A genuine prefixed
           derivation has no prefix-free rival in the Kośa (nirodha offers only
           ni+√rudh), so this only fires on spurious splits: vidyā -> √vid.
        5. A root in the hand-curated Dhātupāṭha core beats one that is not
           (kāra -> √kṛ 08.0010 curated, not √kṝ 06.0145 uncurated).
        6. Failing all else, the longer (more specific) root.
        """
        best = None
        for de, is_verb in self._iter_dhatu_entries(form):
            if krdanta_only and is_verb:
                continue
            dhatu = de.dhatu
            root, verified, curated = self._clean_root(dhatu.aupadeshika)
            # A bare consonant is upstream damage, not a root (see
            # _is_plausible_root); showing √n would teach the reader a root
            # that does not exist, so the reading is dropped entirely.
            if not self._is_plausible_root(root):
                continue
            prefixes = list(dhatu.prefixes or [])
            rank = (
                root == preferred_root,
                is_verb,
                self._initial_fits(root, form, bool(prefixes)),
                curated,
                self._skeleton_fits(root, form),
                not prefixes,
                -len(root),
            )
            if best is None or rank > best[0]:
                gana = self._GANA_NUM.get(str(dhatu.gana)) if dhatu.gana else None
                best = (rank, self._pack(
                    root, prefixes, gana, de.artha_sa, verified, is_verb=is_verb,
                ))
        return best[1] if best else None

    def _resolve_peeled(
        self, form: str, preferred_root: str | None = None
    ) -> dict[str, Any] | None:
        """Strip one canonical prefix and resolve the remaining stem.

        Only nominal (Kṛdanta) readings of the remainder count: a peeled stem
        is a derived noun, so a finite-verb homograph of the remainder would
        be an accident. The privative a-/an- is peeled but never reported as a
        dhātu prefix — it negates the derivative, it is not part of the verb.
        """
        for written in sorted(self._UPASARGAS, key=len, reverse=True):
            if not form.startswith(written):
                continue
            rest = form[len(written):]
            if len(rest) < 3:
                continue
            info = self._best_candidate(rest, krdanta_only=True,
                                        preferred_root=preferred_root)
            if info:
                info["prefixes_slp1"] = [self._UPASARGAS[written]] + info["prefixes_slp1"]
                return info

        for priv in self._PRIVATIVES:
            if not form.startswith(priv):
                continue
            rest = form[len(priv):]
            if len(rest) < 3:
                continue
            info = self._best_candidate(rest, krdanta_only=True,
                                        preferred_root=preferred_root)
            if info:
                return info
        return None

    def describe_root(self, root_slp1: str) -> dict[str, Any] | None:
        """Root info straight from the Dhātupāṭha, for a root we already know.

        Used when the dictionary names a root the Kośa has no derivational
        entry for (karman -> √kṛ): the root is still in the Dhātupāṭha, so its
        class and artha are available even though the derivation is not.
        """
        if not self._ensure() or not root_slp1:
            return None
        assert self._dhatu_kosha is not None
        # The dictionary writes √rañj; the Dhātupāṭha index spells it ranj.
        entries = (self._dhatu_kosha.lookup(root_slp1)
                   or self._dhatu_kosha.lookup(root_slp1.replace("Y", "n")))
        if not entries:
            return None
        best = next((e for e in entries if e.get("curated")), entries[0])
        gana = best.get("gana")
        gana_num = int(gana) if gana is not None and str(gana).isdigit() else None
        return self._pack(
            best.get("core_root") or root_slp1, [],
            gana_num,
            best.get("artha_slp1"), True,
        )

    @staticmethod
    def _pack(
        root_slp1: str,
        prefixes_slp1: list[str],
        gana: int | None,
        artha_slp1: str | None,
        verified: bool,
        is_verb: bool = False,
    ) -> dict[str, Any]:
        return {
            "root_slp1": root_slp1,
            "prefixes_slp1": prefixes_slp1,
            "gana": gana,
            "artha_slp1": artha_slp1,
            "verified": verified,
            "is_verb": is_verb,
        }


_resolver: DhatuResolver | None = None


def get_dhatu_resolver() -> DhatuResolver:
    global _resolver
    if _resolver is None:
        _resolver = DhatuResolver()
    return _resolver
