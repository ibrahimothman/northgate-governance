from __future__ import annotations

import re


_UNINFLECTED = {
    "analysis",
    "basis",
    "crisis",
    "diabetes",
    "news",
    "series",
    "species",
    "status",
}

_IRREGULAR = {
    "children": "child",
    "men": "man",
    "people": "person",
    "women": "woman",
}


def normalize_identifier(text: str) -> str:
    """
    Conservative lexical normalization.

    This function is intentionally deterministic.
    It never invents synonyms or semantic matches.
    """

    text = re.sub(r"[-‐‑‒–—]+", " ", text.strip().casefold())
    words = re.sub(r"\s+", " ", text).split()
    if words:
        # English compound nouns normally inflect at the end. Limiting the
        # operation to that token avoids rewriting meaningful earlier words.
        words[-1] = singularize(words[-1])

    return " ".join(words)


def singularize(word: str) -> str:
    """
    Extremely conservative English singularization.
    """

    if word in _UNINFLECTED:
        return word

    if word in _IRREGULAR:
        return _IRREGULAR[word]

    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"

    if word.endswith("sses"):
        return word[:-2]

    if word.endswith(("ches", "shes")):
        return word[:-2]

    if (
        len(word) > 3
        and word.endswith("s")
        and not word.endswith(("ss", "is", "us"))
    ):
        return word[:-1]

    return word