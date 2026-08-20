from __future__ import annotations

import re

SENTENCE_END = re.compile(r"[.!?][\"']?$")
ABBREVIATIONS = {
    "dr", "jr", "mr", "mrs", "ms", "sr", "st", "vs",
    "a.l", "n.l", "u.s", "no",
}


def split_sentences(description: str) -> list[str]:
    """Split prose without breaking common names, initials, or decimal statistics."""
    words = description.split()
    sentences: list[str] = []
    current: list[str] = []
    for index, word in enumerate(words):
        current.append(word)
        if not SENTENCE_END.search(word) or index == len(words) - 1:
            continue
        bare = word.rstrip(".!?\"'").lower()
        if bare in ABBREVIATIONS or (len(bare) == 1 and bare.isalpha()):
            continue
        sentences.append(" ".join(current))
        current = []
    if current:
        sentences.append(" ".join(current))
    return sentences
