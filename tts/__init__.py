"""Moteurs de synthèse vocale et lecture audio."""

from collections.abc import Callable

from tts.base import TTSConnectionError, TTSEngine, TTSError
from tts.edge_engine import EdgeEngine
from tts.fallback import FallbackEngine
from tts.piper_engine import PiperEngine


def create_engine(notify: Callable[[str], None] = print) -> FallbackEngine:
    """Moteur par défaut : edge-tts, avec bascule automatique vers Piper hors ligne."""
    return FallbackEngine(EdgeEngine(), PiperEngine(), notify=notify)


__all__ = [
    "TTSConnectionError",
    "TTSEngine",
    "TTSError",
    "EdgeEngine",
    "FallbackEngine",
    "PiperEngine",
    "create_engine",
]
