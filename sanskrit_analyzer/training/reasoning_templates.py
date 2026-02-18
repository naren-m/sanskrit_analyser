"""Reasoning templates for disambiguation training data."""

from typing import Any


REASONING_TEMPLATES: dict[str, str] = {
    "case_agreement": (
        "Rule 'case_agreement' matched: {nominative} ({nom_case}) agrees with verb {verb}. "
        "{alternative} has {wrong_case} which cannot be the subject."
    ),
    "verb_agreement": (
        "Rule 'verb_agreement' matched: {verb} is {person}-person {number}, "
        "requiring {expected_subject}. {parse_issue}."
    ),
    "sandhi_preference": (
        "Rule 'sandhi_preference' matched: {preferred_split} follows standard "
        "{sandhi_type} sandhi rules. {alternative_split} would require irregular sandhi."
    ),
    "semantic_coherence": (
        "Rule 'semantic_coherence' matched: {selected_meaning} is contextually "
        "appropriate given {context}. {alternative_meaning} is semantically unlikely here."
    ),
    "word_order": (
        "Rule 'word_order' matched: Standard Sanskrit word order supports {selected_parse}. "
        "{alternative_parse} violates typical {construction_type} construction."
    ),
    "gender_agreement": (
        "Rule 'gender_agreement' matched: {adjective} ({adj_gender}) agrees with "
        "{noun} ({noun_gender}). Parse {rejected_index} incorrectly matches genders."
    ),
}


def fill_template(
    template_name: str,
    **kwargs: str,
) -> str:
    """Fill a reasoning template with specific values.

    Args:
        template_name: Name of the template to use.
        **kwargs: Values to fill in the template.

    Returns:
        Filled reasoning string.

    Raises:
        KeyError: If template_name is not found.
        KeyError: If required template variables are missing.
    """
    if template_name not in REASONING_TEMPLATES:
        raise KeyError(f"Unknown reasoning template: {template_name}")

    template = REASONING_TEMPLATES[template_name]
    return template.format(**kwargs)


def generate_case_agreement_reasoning(
    nominative: str,
    verb: str,
    alternative: str,
    wrong_case: str,
) -> str:
    """Generate reasoning for case agreement rule.

    Args:
        nominative: The word identified as nominative (subject).
        verb: The main verb.
        alternative: The alternative word in rejected parse.
        wrong_case: The incorrect case of the alternative.

    Returns:
        Reasoning string.
    """
    return fill_template(
        "case_agreement",
        nominative=nominative,
        nom_case="nominative",
        verb=verb,
        alternative=alternative,
        wrong_case=wrong_case,
    )


def generate_verb_agreement_reasoning(
    verb: str,
    person: str,
    number: str,
    expected_subject: str,
    parse_issue: str,
) -> str:
    """Generate reasoning for verb agreement rule.

    Args:
        verb: The verb form.
        person: Person of the verb (first/second/third).
        number: Number of the verb (singular/dual/plural).
        expected_subject: What subject the verb expects.
        parse_issue: Description of the issue with rejected parse.

    Returns:
        Reasoning string.
    """
    return fill_template(
        "verb_agreement",
        verb=verb,
        person=person,
        number=number,
        expected_subject=expected_subject,
        parse_issue=parse_issue,
    )


def generate_sandhi_reasoning(
    preferred_split: str,
    sandhi_type: str,
    alternative_split: str,
) -> str:
    """Generate reasoning for sandhi preference rule.

    Args:
        preferred_split: The preferred sandhi split.
        sandhi_type: Type of sandhi (vowel/consonant/visarga).
        alternative_split: The alternative (rejected) split.

    Returns:
        Reasoning string.
    """
    return fill_template(
        "sandhi_preference",
        preferred_split=preferred_split,
        sandhi_type=sandhi_type,
        alternative_split=alternative_split,
    )


def generate_semantic_reasoning(
    selected_meaning: str,
    context: str,
    alternative_meaning: str,
) -> str:
    """Generate reasoning for semantic coherence rule.

    Args:
        selected_meaning: The selected interpretation's meaning.
        context: Contextual information.
        alternative_meaning: The rejected interpretation's meaning.

    Returns:
        Reasoning string.
    """
    return fill_template(
        "semantic_coherence",
        selected_meaning=selected_meaning,
        context=context,
        alternative_meaning=alternative_meaning,
    )


def detect_applicable_rule(
    parses: list[dict[str, Any]],
    selected_index: int,
) -> tuple[str, dict[str, str]]:
    """Detect which reasoning rule applies and extract parameters.

    This is a heuristic function that examines parse differences
    to determine the most applicable reasoning template.

    Args:
        parses: List of parse candidate dictionaries.
        selected_index: Index of the selected parse.

    Returns:
        Tuple of (template_name, template_parameters).
    """
    if len(parses) < 2:
        return "semantic_coherence", {
            "selected_meaning": "the only available interpretation",
            "context": "single parse available",
            "alternative_meaning": "no alternative",
        }

    selected = parses[selected_index]
    rejected_index = 1 - selected_index if selected_index < 2 else 0
    rejected = parses[rejected_index] if rejected_index < len(parses) else parses[0]

    # Default to semantic coherence
    return "semantic_coherence", {
        "selected_meaning": f"Parse {selected_index}",
        "context": "grammatical analysis",
        "alternative_meaning": f"Parse {rejected_index}",
    }
