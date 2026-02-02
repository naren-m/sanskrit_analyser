"""Tests for rule-based disambiguation."""

import pytest

from sanskrit_analyzer.disambiguation.rules import (
    DisambiguationRule,
    FrequencyPreferenceRule,
    GenderNumberAgreementRule,
    ParseCandidate,
    RuleBasedDisambiguator,
    RuleBasedDisambiguatorConfig,
    RuleConfig,
    RuleResult,
    RuleType,
    SandhiPreferenceRule,
)


class TestParseCandidate:
    """Tests for ParseCandidate dataclass."""

    def test_get_lemmas(self) -> None:
        """Test extracting lemmas from segments."""
        candidate = ParseCandidate(
            index=0,
            segments=[
                {"lemma": "gam", "surface": "gacchati"},
                {"lemma": "nara", "surface": "naraḥ"},
            ],
            confidence=0.9,
        )
        lemmas = candidate.get_lemmas()
        assert lemmas == ["gam", "nara"]

    def test_get_lemmas_empty(self) -> None:
        """Test with segments without lemmas."""
        candidate = ParseCandidate(
            index=0,
            segments=[{"surface": "test"}],
            confidence=0.9,
        )
        assert candidate.get_lemmas() == []

    def test_get_morphology(self) -> None:
        """Test getting morphology for a segment."""
        morph = {"gender": "masculine", "number": "singular"}
        candidate = ParseCandidate(
            index=0,
            segments=[{"lemma": "nara", "morphology": morph}],
            confidence=0.9,
        )
        assert candidate.get_morphology(0) == morph
        assert candidate.get_morphology(1) is None


class TestRuleResult:
    """Tests for RuleResult dataclass."""

    def test_create_result(self) -> None:
        """Test creating a rule result."""
        result = RuleResult(
            rule_name="test_rule",
            applied=True,
            confidence_adjustment=0.1,
            reason="Test reason",
            eliminated_parses=[1, 2],
        )
        assert result.rule_name == "test_rule"
        assert result.applied is True
        assert result.confidence_adjustment == 0.1
        assert result.eliminated_parses == [1, 2]


class TestGenderNumberAgreementRule:
    """Tests for GenderNumberAgreementRule."""

    @pytest.fixture
    def rule(self) -> GenderNumberAgreementRule:
        """Create a rule instance."""
        return GenderNumberAgreementRule()

    def test_rule_type(self, rule: GenderNumberAgreementRule) -> None:
        """Test rule type."""
        assert rule.rule_type == RuleType.GRAMMATICAL_AGREEMENT

    def test_disabled_rule(self, rule: GenderNumberAgreementRule) -> None:
        """Test disabled rule returns candidates unchanged."""
        rule.enabled = False
        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.9)
        ]
        result_candidates, result = rule.apply(candidates)
        assert result_candidates == candidates
        assert result.applied is False

    def test_single_candidate(self, rule: GenderNumberAgreementRule) -> None:
        """Test single candidate returns unchanged."""
        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.9)
        ]
        result_candidates, result = rule.apply(candidates)
        assert result_candidates == candidates
        assert result.applied is False

    def test_agreement_valid(self, rule: GenderNumberAgreementRule) -> None:
        """Test candidates with valid agreement pass."""
        candidates = [
            ParseCandidate(
                index=0,
                segments=[
                    {
                        "lemma": "sundara",
                        "pos": "adj",
                        "morphology": {"gender": "masculine", "number": "singular"},
                    },
                    {
                        "lemma": "nara",
                        "pos": "noun",
                        "morphology": {"gender": "masculine", "number": "singular"},
                    },
                ],
                confidence=0.9,
            ),
            ParseCandidate(
                index=1,
                segments=[
                    {
                        "lemma": "sundara",
                        "pos": "adj",
                        "morphology": {"gender": "feminine", "number": "singular"},
                    },
                    {
                        "lemma": "nara",
                        "pos": "noun",
                        "morphology": {"gender": "masculine", "number": "singular"},
                    },
                ],
                confidence=0.8,
            ),
        ]
        result_candidates, result = rule.apply(candidates)
        # Only first candidate should pass (gender matches)
        assert len(result_candidates) == 1
        assert result_candidates[0].index == 0
        assert result.applied is True
        assert 1 in result.eliminated_parses

    def test_agreement_all_eliminated_keeps_original(
        self, rule: GenderNumberAgreementRule
    ) -> None:
        """Test that if all candidates eliminated, original is kept."""
        candidates = [
            ParseCandidate(
                index=0,
                segments=[
                    {
                        "lemma": "sundara",
                        "pos": "adj",
                        "morphology": {"gender": "feminine", "number": "singular"},
                    },
                    {
                        "lemma": "nara",
                        "pos": "noun",
                        "morphology": {"gender": "masculine", "number": "singular"},
                    },
                ],
                confidence=0.9,
            ),
        ]
        result_candidates, result = rule.apply(candidates)
        # Should keep original when all eliminated
        assert len(result_candidates) == 1
        assert result.applied is False


class TestFrequencyPreferenceRule:
    """Tests for FrequencyPreferenceRule."""

    @pytest.fixture
    def rule(self) -> FrequencyPreferenceRule:
        """Create a rule instance."""
        return FrequencyPreferenceRule()

    def test_rule_type(self, rule: FrequencyPreferenceRule) -> None:
        """Test rule type."""
        assert rule.rule_type == RuleType.FREQUENCY

    def test_common_lemma_boost(self, rule: FrequencyPreferenceRule) -> None:
        """Test that common lemmas get boosted."""
        candidates = [
            ParseCandidate(
                index=0,
                segments=[{"lemma": "gam"}],  # Common dhatu
                confidence=0.8,
            ),
            ParseCandidate(
                index=1,
                segments=[{"lemma": "xyz_rare"}],  # Rare word
                confidence=0.8,
            ),
        ]
        result_candidates, result = rule.apply(candidates)

        assert result.applied is True
        # Common lemma should have higher confidence after adjustment
        assert result_candidates[0].confidence > result_candidates[1].confidence

    def test_custom_frequency_data(self) -> None:
        """Test with custom frequency data."""
        frequency_data = {"custom_word": 0.95}
        rule = FrequencyPreferenceRule(frequency_data=frequency_data)

        candidates = [
            ParseCandidate(
                index=0,
                segments=[{"lemma": "custom_word"}],
                confidence=0.8,
            ),
            ParseCandidate(
                index=1,
                segments=[{"lemma": "other"}],
                confidence=0.8,
            ),
        ]
        result_candidates, _ = rule.apply(candidates)
        assert result_candidates[0].segments[0]["lemma"] == "custom_word"


class TestSandhiPreferenceRule:
    """Tests for SandhiPreferenceRule."""

    @pytest.fixture
    def rule(self) -> SandhiPreferenceRule:
        """Create a rule instance."""
        return SandhiPreferenceRule()

    def test_rule_type(self, rule: SandhiPreferenceRule) -> None:
        """Test rule type."""
        assert rule.rule_type == RuleType.SANDHI_PREFERENCE

    def test_common_sandhi_boost(self, rule: SandhiPreferenceRule) -> None:
        """Test that common sandhi types get boosted."""
        candidates = [
            ParseCandidate(
                index=0,
                segments=[{"lemma": "test", "sandhi_info": {"type": "vowel"}}],
                confidence=0.8,
            ),
            ParseCandidate(
                index=1,
                segments=[{"lemma": "test", "sandhi_info": {"type": "exotic"}}],
                confidence=0.8,
            ),
        ]
        result_candidates, result = rule.apply(candidates)

        assert result.applied is True
        # Vowel sandhi should have slightly higher confidence
        assert result_candidates[0].index == 0


class TestRuleBasedDisambiguator:
    """Tests for RuleBasedDisambiguator."""

    @pytest.fixture
    def disambiguator(self) -> RuleBasedDisambiguator:
        """Create a disambiguator instance."""
        return RuleBasedDisambiguator()

    def test_default_rules(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test default rules are registered."""
        rule_names = [r.name for r in disambiguator.rules]
        assert "gender_number_agreement" in rule_names
        assert "frequency_preference" in rule_names
        assert "sandhi_preference" in rule_names

    def test_add_custom_rule(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test adding custom rule."""
        initial_count = len(disambiguator.rules)

        class CustomRule(DisambiguationRule):
            @property
            def rule_type(self) -> RuleType:
                return RuleType.CUSTOM

            def apply(self, candidates, context=None):
                return candidates, RuleResult(rule_name=self.name, applied=False)

        disambiguator.add_rule(CustomRule("custom", 1.0, True))
        assert len(disambiguator.rules) == initial_count + 1

    def test_remove_rule(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test removing a rule."""
        initial_count = len(disambiguator.rules)
        assert disambiguator.remove_rule("frequency_preference") is True
        assert len(disambiguator.rules) == initial_count - 1
        assert disambiguator.remove_rule("nonexistent") is False

    def test_enable_disable_rule(
        self, disambiguator: RuleBasedDisambiguator
    ) -> None:
        """Test enabling and disabling rules."""
        assert disambiguator.disable_rule("frequency_preference") is True
        rule = next(r for r in disambiguator.rules if r.name == "frequency_preference")
        assert rule.enabled is False

        assert disambiguator.enable_rule("frequency_preference") is True
        assert rule.enabled is True

    def test_disambiguate_empty(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test disambiguation with empty candidates."""
        result = disambiguator.disambiguate([])
        assert result == []

    def test_disambiguate_single(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test disambiguation with single candidate."""
        candidates = [
            ParseCandidate(
                index=0,
                segments=[{"lemma": "gam"}],
                confidence=0.9,
            )
        ]
        result = disambiguator.disambiguate(candidates)
        assert len(result) == 1

    def test_disambiguate_multiple(
        self, disambiguator: RuleBasedDisambiguator
    ) -> None:
        """Test disambiguation with multiple candidates."""
        candidates = [
            ParseCandidate(
                index=0,
                segments=[{"lemma": "gam"}],  # Common
                confidence=0.8,
            ),
            ParseCandidate(
                index=1,
                segments=[{"lemma": "rare_word"}],
                confidence=0.8,
            ),
        ]
        result = disambiguator.disambiguate(candidates)
        # Common lemma should be ranked first
        assert result[0].segments[0]["lemma"] == "gam"

    def test_min_confidence_filter(self) -> None:
        """Test minimum confidence threshold."""
        config = RuleBasedDisambiguatorConfig(min_confidence_threshold=0.5)
        disambiguator = RuleBasedDisambiguator(config=config)

        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.6),
            ParseCandidate(index=1, segments=[], confidence=0.2),
        ]
        result = disambiguator.disambiguate(candidates)
        assert len(result) == 1
        assert result[0].index == 0

    def test_max_candidates_limit(self) -> None:
        """Test maximum candidates limit."""
        config = RuleBasedDisambiguatorConfig(max_candidates_to_keep=2)
        disambiguator = RuleBasedDisambiguator(config=config)

        candidates = [
            ParseCandidate(index=i, segments=[], confidence=0.9 - i * 0.1)
            for i in range(5)
        ]
        result = disambiguator.disambiguate(candidates)
        assert len(result) == 2

    def test_get_rule_summary(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test getting rule summary."""
        summary = disambiguator.get_rule_summary()
        assert "gender_number_agreement" in summary
        assert summary["gender_number_agreement"]["enabled"] is True

    def test_last_results(self, disambiguator: RuleBasedDisambiguator) -> None:
        """Test accessing last results."""
        candidates = [
            ParseCandidate(index=0, segments=[], confidence=0.9),
        ]
        disambiguator.disambiguate(candidates)
        results = disambiguator.last_results
        assert len(results) > 0

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RuleBasedDisambiguatorConfig(
            gender_agreement=RuleConfig(enabled=False),
            frequency=RuleConfig(weight=0.8),
        )
        disambiguator = RuleBasedDisambiguator(config=config)

        # Gender agreement should be disabled
        gender_rule = next(
            r for r in disambiguator.rules if r.name == "gender_number_agreement"
        )
        assert gender_rule.enabled is False

        # Frequency should have custom weight
        freq_rule = next(
            r for r in disambiguator.rules if r.name == "frequency_preference"
        )
        assert freq_rule.weight == 0.8
