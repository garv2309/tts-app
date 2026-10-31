"""Découpage du texte en morceaux pour commencer la lecture plus vite."""

import re

from config import CHUNK_MAX_CHARS

# Coupe après . ! ? … (suivis d'un espace) ou à chaque saut de ligne
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    """Découpe le texte en phrases non vides."""
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def _split_long(sentence: str, max_chars: int) -> list[str]:
    """Coupe une phrase trop longue aux espaces, en morceaux d'au plus max_chars."""
    parts: list[str] = []
    current = ""
    for word in sentence.split():
        if current and len(current) + 1 + len(word) > max_chars:
            parts.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        parts.append(current)
    return parts


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Regroupe les phrases en morceaux ; le premier reste court pour démarrer vite."""
    sentences: list[str] = []
    for sentence in split_sentences(text):
        sentences.extend(_split_long(sentence, max_chars))

    chunks: list[str] = []
    for sentence in sentences:
        # Le premier morceau est une seule phrase : la lecture commence dès qu'elle est prête
        if len(chunks) >= 2 and len(chunks[-1]) + 1 + len(sentence) <= max_chars:
            chunks[-1] = f"{chunks[-1]} {sentence}"
        else:
            chunks.append(sentence)
    return chunks
