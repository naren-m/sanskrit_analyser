"""Hand-curated word lists used to disambiguate kosha candidate analyses.

Both lists are keyed by SLP1 (the engine's internal scheme).
"""

# Particles that never inflect (avyaya). A surface form in this set resolves
# to the indeclinable reading only; vidyut's verb/root readings of it
# (e.g. ca -> root ci) are spurious.
PARTICLES = frozenset({
    "ca", "tu", "na", "iti", "hi", "eva", "api", "vA", "aTa", "iva", "Kalu",
    "taTA", "yaTA", "uta", "evam", "kila", "nanu", "sma", "ha", "punaH",
    "yadi", "tarhi", "yatra", "tatra", "atra", "yAvat", "tAvat", "yadA",
    "tadA", "cet", "svit",
})

# Names shared across the Ramayana and Mahabharata. Hand-picked and generic to
# the epics, not an exhaustive onomasticon: a stem or lemma in this set is a
# nominal (proper noun), so its verb-root readings (rAma -> root ra) are dropped.
PROPER_NOUNS = frozenset({
    "rAma", "sItA", "lakzmaRa", "rAvaRa", "hanumat", "Barata", "daSaratha",
    "kfzRa", "arjuna", "sugrIva", "vAlin", "vibhIzaRa", "kOsalyA", "kEkeyI",
    "sumitrA", "janaka", "indrajit", "yuDizWira", "BIma", "nakula",
    "sahadeva", "karRa", "duryoDana", "draupadI",
})
