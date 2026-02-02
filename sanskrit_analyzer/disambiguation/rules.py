"""Rule-based disambiguation for Sanskrit parse filtering."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RuleType(Enum):
    """Types of disambiguation rules."""

    GRAMMATICAL_AGREEMENT = "grammatical_agreement"
    FREQUENCY = "frequency"
    SANDHI_PREFERENCE = "sandhi_preference"
    SEMANTIC = "semantic"
    CUSTOM = "custom"


@dataclass
class RuleResult:
    """Result from applying a disambiguation rule."""

    rule_name: str
    applied: bool
    confidence_adjustment: float = 0.0
    reason: Optional[str] = None
    eliminated_parses: list[int] = field(default_factory=list)


@dataclass
class ParseCandidate:
    """A parse candidate for disambiguation."""

    index: int
    segments: list[dict[str, Any]]
    confidence: float
    engine_votes: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_lemmas(self) -> list[str]:
        """Get all lemmas from segments."""
        return [s.get("lemma", "") for s in self.segments if s.get("lemma")]

    def get_morphology(self, index: int) -> Optional[dict[str, Any]]:
        """Get morphology for a segment."""
        if 0 <= index < len(self.segments):
            return self.segments[index].get("morphology")
        return None


class DisambiguationRule(ABC):
    """Abstract base class for disambiguation rules."""

    def __init__(
        self,
        name: str,
        weight: float = 1.0,
        enabled: bool = True,
    ) -> None:
        """Initialize the rule.

        Args:
            name: Rule name for logging and tracking.
            weight: Weight for confidence adjustments.
            enabled: Whether the rule is active.
        """
        self.name = name
        self.weight = weight
        self.enabled = enabled

    @property
    @abstractmethod
    def rule_type(self) -> RuleType:
        """Return the type of this rule."""
        pass

    @abstractmethod
    def apply(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[list[ParseCandidate], RuleResult]:
        """Apply the rule to filter or rerank candidates.

        Args:
            candidates: List of parse candidates to evaluate.
            context: Optional context (previous/next sentences, etc.).

        Returns:
            Tuple of (filtered candidates, rule result).
        """
        pass


class GenderNumberAgreementRule(DisambiguationRule):
    """Rule for adjective-noun gender/number agreement.

    In Sanskrit, adjectives must agree with nouns in gender, number, and case.
    This rule filters out parses where adjacent adjective-noun pairs disagree.
    """

    def __init__(self, weight: float = 1.0, enabled: bool = True) -> None:
        super().__init__("gender_number_agreement", weight, enabled)

    @property
    def rule_type(self) -> RuleType:
        return RuleType.GRAMMATICAL_AGREEMENT

    def apply(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[list[ParseCandidate], RuleResult]:
        if not self.enabled or len(candidates) <= 1:
            return candidates, RuleResult(
                rule_name=self.name,
                applied=False,
                reason="Rule disabled or single candidate",
            )

        valid_candidates: list[ParseCandidate] = []
        eliminated: list[int] = []

        for candidate in candidates:
            if self._check_agreement(candidate):
                valid_candidates.append(candidate)
            else:
                eliminated.append(candidate.index)

        # If all eliminated, keep original (rule too strict)
        if not valid_candidates:
            return candidates, RuleResult(
                rule_name=self.name,
                applied=False,
                reason="All candidates eliminated, keeping original",
            )

        return valid_candidates, RuleResult(
            rule_name=self.name,
            applied=len(eliminated) > 0,
            confidence_adjustment=0.1 * self.weight if eliminated else 0.0,
            reason=f"Eliminated {len(eliminated)} parses with agreement violations",
            eliminated_parses=eliminated,
        )

    def _check_agreement(self, candidate: ParseCandidate) -> bool:
        """Check if adjective-noun pairs agree in the parse."""
        segments = candidate.segments

        for i in range(len(segments) - 1):
            seg1 = segments[i]
            seg2 = segments[i + 1]

            # Check if we have an adj-noun pair
            pos1 = seg1.get("pos", "")
            pos2 = seg2.get("pos", "")

            if self._is_adjective(pos1) and self._is_noun(pos2):
                if not self._check_pair_agreement(seg1, seg2):
                    return False
            elif self._is_noun(pos1) and self._is_adjective(pos2):
                if not self._check_pair_agreement(seg1, seg2):
                    return False

        return True

    def _is_adjective(self, pos: str) -> bool:
        """Check if POS tag indicates adjective."""
        adj_tags = {"adj", "adjective", "a", "विशेषण"}
        return pos.lower() in adj_tags

    def _is_noun(self, pos: str) -> bool:
        """Check if POS tag indicates noun."""
        noun_tags = {"n", "noun", "substantive", "नाम", "संज्ञा"}
        return pos.lower() in noun_tags

    def _check_pair_agreement(
        self, seg1: dict[str, Any], seg2: dict[str, Any]
    ) -> bool:
        """Check if two segments agree in gender, number, case."""
        morph1 = seg1.get("morphology", {})
        morph2 = seg2.get("morphology", {})

        if not morph1 or not morph2:
            # Can't check, assume OK
            return True

        # Check gender
        gender1 = morph1.get("gender")
        gender2 = morph2.get("gender")
        if gender1 and gender2 and gender1 != gender2:
            return False

        # Check number
        number1 = morph1.get("number")
        number2 = morph2.get("number")
        if number1 and number2 and number1 != number2:
            return False

        # Check case
        case1 = morph1.get("case")
        case2 = morph2.get("case")
        if case1 and case2 and case1 != case2:
            return False

        return True


class FrequencyPreferenceRule(DisambiguationRule):
    """Rule for preferring more common word forms.

    Uses frequency data to boost confidence for common forms
    and reduce confidence for rare forms.
    """

    # Common Sanskrit verb roots (high frequency)
    COMMON_DHATUS: set[str] = {
        "gam",
        "kṛ",
        "bhū",
        "as",
        "vac",
        "dā",
        "dṛś",
        "vid",
        "śru",
        "pat",
        "sthā",
        "han",
        "jan",
        "car",
        "nī",
        "yuj",
        "budh",
        "man",
        "vṛt",
        "labh",
    }

    # Common lemmas
    COMMON_LEMMAS: set[str] = {
        "rāma",
        "sītā",
        "deva",
        "nara",
        "vana",
        "gṛha",
        "putra",
        "pitṛ",
        "mātṛ",
        "rājan",
        "brahman",
        "ātman",
        "karma",
        "dharma",
        "artha",
        "kāma",
        "mokṣa",
    }

    def __init__(
        self,
        weight: float = 0.5,
        enabled: bool = True,
        frequency_data: Optional[dict[str, float]] = None,
    ) -> None:
        super().__init__("frequency_preference", weight, enabled)
        self._frequency_data = frequency_data or {}

    @property
    def rule_type(self) -> RuleType:
        return RuleType.FREQUENCY

    def apply(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[list[ParseCandidate], RuleResult]:
        if not self.enabled or len(candidates) <= 1:
            return candidates, RuleResult(
                rule_name=self.name,
                applied=False,
                reason="Rule disabled or single candidate",
            )

        # Score each candidate by frequency
        scored: list[tuple[ParseCandidate, float]] = []
        for candidate in candidates:
            score = self._calculate_frequency_score(candidate)
            scored.append((candidate, score))

        # Sort by score (highest first)
        scored.sort(key=lambda x: x[1], reverse=True)

        # Adjust confidences based on frequency
        result_candidates: list[ParseCandidate] = []
        max_score = scored[0][1] if scored else 0.0

        for candidate, score in scored:
            if max_score > 0:
                adjustment = (score / max_score) * 0.1 * self.weight
                candidate.confidence = min(1.0, candidate.confidence + adjustment)
            result_candidates.append(candidate)

        return result_candidates, RuleResult(
            rule_name=self.name,
            applied=True,
            confidence_adjustment=0.1 * self.weight,
            reason=f"Adjusted confidence based on frequency for {len(candidates)} candidates",
        )

    def _calculate_frequency_score(self, candidate: ParseCandidate) -> float:
        """Calculate frequency score for a parse candidate."""
        score = 0.0
        lemmas = candidate.get_lemmas()

        for lemma in lemmas:
            # Check custom frequency data
            if lemma in self._frequency_data:
                score += self._frequency_data[lemma]
            # Check common dhatus
            elif lemma.lower() in self.COMMON_DHATUS:
                score += 0.8
            # Check common lemmas
            elif lemma.lower() in self.COMMON_LEMMAS:
                score += 0.7
            else:
                score += 0.3  # Default score

        return score / max(len(lemmas), 1)


class SandhiPreferenceRule(DisambiguationRule):
    """Rule for preferring standard sandhi forms.

    Prefers parses that use common sandhi rules over exotic ones.
    """

    # Common sandhi types (higher preference)
    COMMON_SANDHI: set[str] = {
        "vowel",
        "savarna_dirgha",
        "guna",
        "vrddhi",
        "visarga",
    }

    def __init__(self, weight: float = 0.3, enabled: bool = True) -> None:
        super().__init__("sandhi_preference", weight, enabled)

    @property
    def rule_type(self) -> RuleType:
        return RuleType.SANDHI_PREFERENCE

    def apply(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[list[ParseCandidate], RuleResult]:
        if not self.enabled or len(candidates) <= 1:
            return candidates, RuleResult(
                rule_name=self.name,
                applied=False,
                reason="Rule disabled or single candidate",
            )

        # Score each candidate by sandhi preference
        for candidate in candidates:
            adjustment = self._calculate_sandhi_preference(candidate)
            candidate.confidence = min(1.0, candidate.confidence + adjustment)

        # Sort by adjusted confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)

        return candidates, RuleResult(
            rule_name=self.name,
            applied=True,
            confidence_adjustment=0.05 * self.weight,
            reason="Adjusted confidence based on sandhi preferences",
        )

    def _calculate_sandhi_preference(self, candidate: ParseCandidate) -> float:
        """Calculate sandhi preference adjustment."""
        total_adjustment = 0.0
        sandhi_count = 0

        for segment in candidate.segments:
            sandhi_info = segment.get("sandhi_info", {})
            sandhi_type = sandhi_info.get("type", "").lower()

            if sandhi_type:
                sandhi_count += 1
                if sandhi_type in self.COMMON_SANDHI:
                    total_adjustment += 0.1 * self.weight
                else:
                    total_adjustment -= 0.05 * self.weight

        return total_adjustment / max(sandhi_count, 1)


@dataclass
class RuleConfig:
    """Configuration for a disambiguation rule."""

    enabled: bool = True
    weight: float = 1.0


@dataclass
class RuleBasedDisambiguatorConfig:
    """Configuration for the rule-based disambiguator."""

    gender_agreement: RuleConfig = field(default_factory=RuleConfig)
    frequency: RuleConfig = field(default_factory=lambda: RuleConfig(weight=0.5))
    sandhi: RuleConfig = field(default_factory=lambda: RuleConfig(weight=0.3))
    min_confidence_threshold: float = 0.3
    max_candidates_to_keep: int = 5


class RuleBasedDisambiguator:
    """Applies rule-based disambiguation to filter and rank parse candidates.

    The disambiguator applies a configurable set of rules in order:
    1. Grammatical agreement (gender/number/case)
    2. Frequency preference (common forms)
    3. Sandhi preference (common sandhi types)

    Each rule can filter candidates or adjust their confidence scores.

    Example:
        disambiguator = RuleBasedDisambiguator()
        filtered = disambiguator.disambiguate(candidates)
    """

    def __init__(
        self,
        config: Optional[RuleBasedDisambiguatorConfig] = None,
        custom_rules: Optional[list[DisambiguationRule]] = None,
    ) -> None:
        """Initialize the disambiguator.

        Args:
            config: Configuration for built-in rules.
            custom_rules: Additional custom rules to apply.
        """
        self._config = config or RuleBasedDisambiguatorConfig()
        self._rules: list[DisambiguationRule] = []
        self._results: list[RuleResult] = []

        # Add built-in rules
        self._rules.append(
            GenderNumberAgreementRule(
                weight=self._config.gender_agreement.weight,
                enabled=self._config.gender_agreement.enabled,
            )
        )
        self._rules.append(
            FrequencyPreferenceRule(
                weight=self._config.frequency.weight,
                enabled=self._config.frequency.enabled,
            )
        )
        self._rules.append(
            SandhiPreferenceRule(
                weight=self._config.sandhi.weight,
                enabled=self._config.sandhi.enabled,
            )
        )

        # Add custom rules
        if custom_rules:
            self._rules.extend(custom_rules)

    @property
    def rules(self) -> list[DisambiguationRule]:
        """Get all registered rules."""
        return self._rules

    @property
    def last_results(self) -> list[RuleResult]:
        """Get results from the last disambiguation run."""
        return self._results

    def add_rule(self, rule: DisambiguationRule) -> None:
        """Add a custom rule.

        Args:
            rule: Rule to add.
        """
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.

        Args:
            name: Name of the rule to remove.

        Returns:
            True if removed, False if not found.
        """
        initial_count = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < initial_count

    def enable_rule(self, name: str) -> bool:
        """Enable a rule by name.

        Args:
            name: Name of the rule to enable.

        Returns:
            True if found and enabled.
        """
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, name: str) -> bool:
        """Disable a rule by name.

        Args:
            name: Name of the rule to disable.

        Returns:
            True if found and disabled.
        """
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = False
                return True
        return False

    def disambiguate(
        self,
        candidates: list[ParseCandidate],
        context: Optional[dict[str, Any]] = None,
    ) -> list[ParseCandidate]:
        """Apply all rules to disambiguate parse candidates.

        Args:
            candidates: List of parse candidates to disambiguate.
            context: Optional context for rules.

        Returns:
            Filtered and ranked list of candidates.
        """
        if not candidates:
            return []

        self._results = []
        current = candidates.copy()

        # Apply each rule in order
        for rule in self._rules:
            if not rule.enabled:
                continue

            current, result = rule.apply(current, context)
            self._results.append(result)

            if result.applied:
                logger.debug(
                    "Rule %s applied: %s", rule.name, result.reason
                )

        # Filter by minimum confidence
        current = [
            c for c in current
            if c.confidence >= self._config.min_confidence_threshold
        ]

        # Sort by confidence (highest first)
        current.sort(key=lambda c: c.confidence, reverse=True)

        # Limit number of candidates
        return current[: self._config.max_candidates_to_keep]

    def get_rule_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of all rules and their status.

        Returns:
            Dictionary with rule information.
        """
        return {
            rule.name: {
                "type": rule.rule_type.value,
                "weight": rule.weight,
                "enabled": rule.enabled,
            }
            for rule in self._rules
        }
