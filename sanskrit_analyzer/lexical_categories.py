"""Curated lexical categories: facts about Sanskrit words, not about any one text.

Three closed word lists, keyed by the romanised (ASCII) form of a lemma or
surface form, for scripture apps that must keep generic words from being
treated as individuals:

- ``ROLE_NOUN_KEYS``: common nouns naming a relational role.
- ``PRONOUN_KEYS``: pronouns and indeclinable particles.
- ``GENERIC_EPITHET_KEYS``: epithets any hero, sage or king can bear.

The lists are curated by hand, not derived from glosses.
"""

from __future__ import annotations

#: Common nouns naming a *relational role* rather than an individual. Every
#: bearer of the role collapses into one node when such a word is treated as an
#: entity: ``वीर`` ("hero") would merge every hero, and ``पुत्र`` ("son") every
#: father's son. Intended for matching against an entity's *primary* key only.
#: जनक is pointedly absent: *janaka* also means "father", but Janaka is
#: a person, which is why this list is curated and not derived from glosses.
ROLE_NOUN_KEYS: frozenset[str] = frozenset({
    # kinship roles
    "putra", "suta", "atmaja", "tanaya", "duhitri", "bharya", "patni",
    "patnigana", "pitri", "matri", "bhratri", "anuja", "agraja", "snusha",
    # social / life-stage roles
    "kumara", "bala", "shishya", "guru", "dvija", "tapodhana",
    # generic person nouns and honorifics
    "vira", "purusha", "nara", "manava", "nari", "stri", "rajan", "nripa",
    "bhagavan",
    # collective abstractions
    "kula", "vamsha",
    # troop and species collectives: armies become grammatical subjects, so a
    # reader binds them as entities whose "relations" are whichever member the
    # verse actually meant
    "vanara", "vriksavanara", "vrikshavanara", "rakshasa", "deva", "pannaga",
    "simha", "naga", "bhuta",
    # office or rank held by many people
    "mantri", "raj", "prabhu",
    # adjectives, adverbs and pronouns a reader may bind as if they named
    # someone ("gatimatam" is a genitive plural, "of the swift ones")
    "gatimatam", "anya", "purvam", "sarva",
    # epithets standing where a name should: both of these are one specific
    # person under a description, so the edges belong on राम and रावण, not on a
    # node named after the description
    "purushottamam", "rakshasamishvaram", "mahatman", "mahabala",
    # battlefield objects, countless and interchangeable
    "shara", "sharah", "ratha", "shula",
    # "battle" (रणा/रणम्/रणं/रणे): the target of "kills in battle" is the war,
    # not a participant
    "rana", "ranam", "rane",
})

#: Pronouns and indeclinable particles a reader may register as entities. A
#: closed class — unlike epithets, it will not grow as more text is read — so a
#: list is the honest tool. Left unfiltered, ``अहं`` ("I") and ``मया`` ("by
#: me") accumulate huge degree, because every "I said" lands on whichever
#: character last claimed ``मम`` as an alias. Keys are the English forms
#: derived from the Devanagari (``अहं`` → ``aham``).
PRONOUN_KEYS: frozenset[str] = frozenset({
    # first and second person
    "aham", "ahm", "maya", "mama", "mam", "me", "mayi", "asmat",
    "vayam", "nah", "asmakam", "asmabhih", "asman",
    "tvam", "tva", "tvaya", "tava", "te", "tvayi", "tvat",
    "yuyam", "vah", "yushmakam", "yushman", "bhavan", "bhavantam", "bhavata",
    # third person and demonstratives
    "sah", "sa", "tam", "tasya", "tena", "tasmai", "tasmat", "tasmin", "tat",
    "tani", "tau", "tan", "taih", "tesham", "tebhyah", "teshu", "tasyah",
    "tasyam", "taya", "tayoh",
    "ayam", "idam", "iyam", "imam", "asya", "asmai", "anena", "asmin",
    "esha", "eshah", "etat", "etam", "etad", "etasya", "ete", "etan",
    "asau", "amum",
    # relative, interrogative, reflexive (``ka`` and ``atman`` are left out:
    # Ka is a name of Prajāpati and आत्मन् a concept the epic discusses)
    "yah", "yam", "yasya", "yena", "yat", "ye", "yan", "yesham", "yasyah",
    "kah", "kam", "kasya", "kena", "kim", "ke", "kesham",
    "svayam",
    # particles, conjunctions, adverbs of place and time
    "iti", "eva", "ca", "tu", "hi", "atha", "api", "na", "vai", "iva",
    "tatha", "yatha", "tada", "yada", "tatra", "atra", "yatra", "kutra",
    "evam", "tatah", "yatah", "itah", "kutah", "punah", "adya", "idanim",
    "sada", "kadacit", "kimcit", "kascit", "kecit",
})

#: Epithets any hero, sage or king can bear. They identify a *quality*, not a
#: person, so as match keys they hand one entity's questions to another —
#: वाल्मीकि and विश्वामित्र both claimed ``munivara``, and ``dharmatma`` rode
#: along on whichever node the reader happened to attach it to. Intended to be
#: stripped from aliases only; an entity whose *name* is one of these keeps it.
GENERIC_EPITHET_KEYS: frozenset[str] = frozenset({
    "dharmatma", "dharmatmana", "dharmavit", "mahatma", "mahatman",
    "mahabaho", "mahabhaga", "mahatejas", "munivara", "muni", "vira", "viran",
    "narashreshtha", "narashardula", "rajashardula", "purusharshabha",
    "narottama", "purushottama", "narendra", "rajendra", "raja", "rajan",
    "prabho", "prabhu", "saumya", "tata", "dhimat", "vakyavisharada",
    "shatru", "deva", "devah",
})
