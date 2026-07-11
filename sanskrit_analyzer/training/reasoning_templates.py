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


# Morphological dimensions compared between parses, in priority order.  The
# first dimension on which the selected and rejected parse disagree decides
# which reasoning template applies.
_MORPH_KEYS = ("case", "person", "number", "gender", "voice", "tense", "pos")


def _collect_morphology(parse: dict[str, Any]) -> dict[str, str]:
    """Flatten a parse's morphological features into a comparable dict.

    Features are read from the parse's top-level keys and from any nested
    word list (``words``/``base_words``/``segments``), so parses expressed
    either as flat dicts or as ``{"words": [...]}`` are both comparable.
    """
    feats: dict[str, str] = {}
    for key in _MORPH_KEYS:
        value = parse.get(key)
        if value is not None:
            feats[key] = str(value)
    for list_key in ("words", "base_words", "segments"):
        for word in parse.get(list_key) or []:
            if isinstance(word, dict):
                for key in _MORPH_KEYS:
                    value = word.get(key)
                    if value is not None:
                        feats.setdefault(key, str(value))
    return feats


def _split_signature(parse: dict[str, Any]) -> str:
    """Return a string describing how a parse segments the surface text."""
    for list_key in ("segments", "sandhi_groups", "words", "base_words"):
        items = parse.get(list_key)
        if items:
            parts = [
                str(it.get("surface_form") or it.get("surface") or it.get("lemma") or it)
                if isinstance(it, dict)
                else str(it)
                for it in items
            ]
            return " + ".join(parts)
    return str(parse.get("split", ""))


def _first_other_index(selected_index: int, count: int) -> int:
    """Return the index of a parse other than *selected_index*."""
    for i in range(count):
        if i != selected_index:
            return i
    return selected_index


def detect_applicable_rule(
    parses: list[dict[str, Any]],
    selected_index: int,
) -> tuple[str, dict[str, str]]:
    """Detect which reasoning rule applies and extract parameters.

    Compares the selected parse against a rejected alternative and picks the
    reasoning template for the first morphological dimension on which they
    disagree (case -> verb agreement -> gender -> sandhi -> word order),
    falling back to semantic coherence when no structural difference is
    found.  This makes every template reachable and ties the generated
    reasoning to the actual differences between the candidates rather than
    always returning a single constant rule.

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
    rejected_index = _first_other_index(selected_index, len(parses))
    rejected = parses[rejected_index]

    sel = _collect_morphology(selected)
    rej = _collect_morphology(rejected)

    sel_interp = str(selected.get("interpretation") or f"Parse {selected_index}")
    rej_interp = str(rejected.get("interpretation") or f"Parse {rejected_index}")

    def _differs(key: str) -> bool:
        return key in sel and key in rej and sel[key] != rej[key]

    # 1. Case disagreement -> case agreement rule.
    if _differs("case"):
        return "case_agreement", {
            "nominative": sel_interp,
            "nom_case": sel["case"],
            "verb": str(selected.get("verb") or "the verb"),
            "alternative": rej_interp,
            "wrong_case": rej["case"],
        }

    # 2. Verb person/number disagreement -> verb agreement rule.
    if _differs("person") or _differs("number"):
        mismatch = "person" if _differs("person") else "number"
        return "verb_agreement", {
            "verb": str(selected.get("verb") or sel_interp),
            "person": sel.get("person", "third"),
            "number": sel.get("number", "singular"),
            "expected_subject": sel_interp,
            "parse_issue": f"Parse {rejected_index} disagrees in {mismatch}",
        }

    # 3. Gender disagreement -> gender agreement rule.
    if _differs("gender"):
        return "gender_agreement", {
            "adjective": sel_interp,
            "adj_gender": sel["gender"],
            "noun": str(selected.get("noun") or "the noun"),
            "noun_gender": sel["gender"],
            "rejected_index": str(rejected_index),
        }

    # 4. Different segmentation -> sandhi preference rule.
    sel_split = _split_signature(selected)
    rej_split = _split_signature(rejected)
    if sel_split and rej_split and sel_split != rej_split:
        return "sandhi_preference", {
            "preferred_split": sel_split,
            "sandhi_type": str(selected.get("sandhi_type") or "vowel"),
            "alternative_split": rej_split,
        }

    # 5. Same features but a different reading -> word order rule.
    if sel_interp != rej_interp and (sel or rej):
        return "word_order", {
            "selected_parse": sel_interp,
            "alternative_parse": rej_interp,
            "construction_type": str(
                selected.get("construction_type") or "subject-object-verb"
            ),
        }

    # 6. Fallback: semantic coherence, using the real interpretations.
    return "semantic_coherence", {
        "selected_meaning": sel_interp,
        "context": str(selected.get("context") or "grammatical analysis"),
        "alternative_meaning": rej_interp,
    }
