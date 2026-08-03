"""Tests for DhatuResolver — vidyut-Kośa root recovery.

Skips gracefully when the vidyut data bundle is absent (e.g. minimal CI
without the data bundle).
"""
import pytest

from sanskrit_analyzer.dhatu.resolver import DhatuResolver


@pytest.fixture(scope="module")
def resolver():
    r = DhatuResolver()
    if not r._ensure():
        pytest.skip("vidyut Kośa unavailable")
    return r


class TestDhatuResolver:
    def test_derived_noun_maps_to_root(self, resolver):
        """yoga (a nominal stem, not a verb) -> √yuj with its gaṇa + gloss."""
        info = resolver.resolve("yogaH", "yoga")
        assert info is not None
        assert info["root_slp1"] == "yuj"
        assert info["verified"] is True
        assert info["gana"] == 10  # curādi
        assert info["artha_slp1"]  # saMyamane
        assert info["is_verb"] is False

    def test_prefixed_derivative_keeps_prefix(self, resolver):
        """nirodha -> ni + √rudh (prefix surfaced separately)."""
        info = resolver.resolve("niroDaH", "niroDa")
        assert info is not None
        assert info["root_slp1"] == "ruD"
        assert info["prefixes_slp1"] == ["ni"]

    def test_finite_verb_flagged(self, resolver):
        """A finite form resolves to its root and is flagged a verb."""
        info = resolver.resolve("Bavati", "BU")
        assert info is not None
        assert info["root_slp1"] == "BU"
        assert info["is_verb"] is True
        assert info["gana"] == 1  # bhvādi

    def test_retroflex_root_cleaned(self, resolver):
        """draṣṭṛ -> √dṛś (residual it-marker stripped, curated-verified)."""
        info = resolver.resolve("drazwf", "drazwf")
        assert info is not None
        assert info["root_slp1"] == "dfS"

    def test_particle_has_no_root(self, resolver):
        """Indeclinables/particles legitimately return None."""
        assert resolver.resolve("aTa", "aTa") is None


class TestUpasargaPeeling:
    """The Kośa files upasarga-prefixed stems as *Basic* pratipādikas with no
    dhātu link, while the bare derivative is a Kṛdanta that has one. Peeling a
    canonical upasarga recovers the root and reports the prefix."""

    def test_prefixed_stem_recovers_root(self, resolver):
        """anuśāsana ('teaching', sutra 1.1) -> anu + √śās."""
        info = resolver.resolve("anuSAsanam", "anuSAsana")
        assert info is not None
        assert info["root_slp1"] == "SAs"
        assert info["prefixes_slp1"] == ["anu"]

    def test_privative_stem_recovers_root(self, resolver):
        """akliṣṭa ('un-afflicted', sutra 1.5) -> √kliś; a- is not a prefix."""
        info = resolver.resolve("aklizwAH", "aklizwa")
        assert info is not None
        assert info["root_slp1"] == "kliS"
        assert "a" not in info["prefixes_slp1"]

    def test_peeling_never_fires_on_particles(self, resolver):
        """A peelable-looking indeclinable must still return None."""
        assert resolver.resolve("api", "api") is None
        assert resolver.resolve("tatra", "tatra") is None


class TestCitationSpelledIndexKeys:
    """The Dhātupāṭha indexes roots under their *citation* spelling: an initial
    s is written ṣ and an initial n is written ṇ (P. 6.1.64-65 read in
    reverse), so √sidh is filed as ṣidh. Normalising the spelling before the
    index lookup asks for a key that does not exist, so a real root comes back
    unverified — and the adapter drops unverified roots. 90 of the index's 97
    citation-spelled roots are reachable only under the cited key."""

    def test_citation_spelled_root_verifies(self, resolver):
        """siddhi -> √sidh, attested (filed as ṣidh 01.0450 'gatyām')."""
        info = resolver.resolve("sidDi")
        assert info is not None
        assert info["root_slp1"] == "siD"
        assert info["verified"] is True, "√sidh is in the Dhātupāṭha as ṣidh"
        assert info["gana"] == 1
        assert info["artha_slp1"]

    def test_clean_root_finds_root_under_cited_key(self, resolver):
        """_clean_root reports the real spelling but must still verify."""
        root, verified, _curated = resolver._clean_root("zi\\Du~")
        assert root == "siD"
        assert verified is True

    def test_cited_key_root_is_never_displayed(self, resolver):
        """Verification via the cited key must not leak ṣ/ṇ into the output."""
        info = resolver.resolve("sidDi")
        assert not info["root_slp1"].startswith(("z", "R"))


class TestLeadingItMarkers:
    """Some roots carry an it-marker *before* the root (P. 1.3.2ff): √hā is
    cited ohāk, √vij is ovijī. The marker's tilde looks exactly like the tail
    of a trailing nasal-infix residue (rudhi~), so stripping the residue first
    consumes the whole root and leaves the bare marker vowel. Twelve
    Dhātupāṭha roots are lost that way, √hā 'to abandon' among them."""

    def test_leading_o_marker_keeps_root(self, resolver):
        """ohāk -> √hā 'tyāge', not the marker vowel 'o'."""
        root, verified, _ = resolver._clean_root("o~hA\\k")
        assert root == "hA", "leading o~ must come off before the residue rule"
        assert verified is True

    def test_leading_marker_root_verifies_under_its_index_key(self, resolver):
        """The index files some of these keeping the marker (core_root o~vij)."""
        root, verified, _ = resolver._clean_root("o~vijI~\\")
        assert root == "vij"
        assert verified is True

    def test_marker_vowel_never_becomes_a_root(self, resolver):
        """No single marker vowel may ever be reported as a dhātu."""
        for aupadeshika in ("o~hA\\N", "o~vE\\", "wuo~Svi", "o~vrascU~"):
            root, _, _ = resolver._clean_root(aupadeshika)
            assert root not in ("o", "u", ""), f"{aupadeshika} collapsed to {root!r}"


class TestImplausibleRoots:
    """The Dhātupāṭha index reduces a few roots to a single consonant — it
    reads the ghu- of ghuṇa/ghuṭa/ghuṣa as an it-marker and files √ghuṇ under
    'ṇ'. No Sanskrit root is a bare consonant (single-*vowel* roots such as
    √ṛ and √i are real and must survive), so such an entry is upstream damage
    and is better shown as nothing than as a confident √n."""

    def test_ghu_root_now_resolves_properly(self, resolver):
        """Task 2 fixed this at source: √ghuṇ keeps its initial and verifies."""
        root, verified, _ = resolver._clean_root("GuRa~")
        assert root == "GuR"
        assert verified is True

    def test_implausible_root_is_never_reported(self, resolver):
        """No reading may reach the caller with a bare-consonant root."""
        assert not resolver._is_plausible_root("n")
        assert not resolver._is_plausible_root("z")
        assert not resolver._is_plausible_root("-")

    def test_single_vowel_roots_survive(self, resolver):
        """√i and √ṛ are genuine one-letter roots."""
        for aupadeshika, expected in (("i\\N", "i"), ("f\\", "f")):
            root, verified, _ = resolver._clean_root(aupadeshika)
            assert root == expected
            assert verified is True

    def test_placeholder_entry_is_not_a_root(self, resolver):
        assert resolver._clean_root("-")[0] != "-" or not resolver._clean_root("-")[1]


class TestSurfaceOnlyReadings:
    """When only the inflected surface resolves, whether to trust it depends
    on the root it produced. A root that underlies the lemma says the same
    thing for every inflection of the word; a root that is a stranger to the
    lemma was chosen by the case ending and will disagree with the word's
    other occurrences."""

    def test_keeps_a_root_that_underlies_the_lemma(self, resolver):
        """kliṣṭa -> √kliś, and the lemma kliś *is* that root."""
        info = resolver.resolve("klizwa", "kliS")
        assert info is not None and info["root_slp1"] == "kliS"

    def test_discards_a_root_foreign_to_the_lemma(self, resolver):
        """viṣayam matched a vi+√siv 'to sew' krdanta; viṣaya is not from
        √siv, and the word's other occurrences do not say so."""
        info = resolver.resolve("vizayam", "vizaya")
        assert info is None or info["root_slp1"] != "siv"

    def test_a_finite_verb_still_wins_from_its_surface(self, resolver):
        """√bhū lives in bhavati, not in any nominal reading of the stem."""
        info = resolver.resolve("Bavati", "BU")
        assert info is not None and info["root_slp1"] == "BU"
        assert info["is_verb"] is True


class TestRootDisambiguation:
    """Several Kṛdanta entries can share a stem; first-wins picks wrong roots."""

    def test_vidya_is_from_vid_not_da(self, resolver):
        """vidyā 'knowledge' is √vid 'know', not vi + √dā 'give'."""
        info = resolver.resolve("vidyA", "vidyA")
        assert info is not None
        assert info["root_slp1"] == "vid"
        assert info["prefixes_slp1"] == []

    def test_kara_is_from_kr_not_kr_long(self, resolver):
        """kāra 'doing' is √kṛ, not √kṝ 'scatter'."""
        info = resolver.resolve("kAra", "kAra")
        assert info is not None
        assert info["root_slp1"] == "kf"
