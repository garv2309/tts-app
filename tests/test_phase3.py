"""Tests de la phase 3 : découpage, bascule hors ligne, Piper."""

from pathlib import Path

import pytest

from config import PIPER_VOICES_DIR
from tts import FallbackEngine, PiperEngine, TTSConnectionError, TTSEngine, TTSError
from tts.text_utils import chunk_text, split_sentences

# --- Découpage du texte ---


def test_split_sentences() -> None:
    text = "Bonjour. Comment ça va ? Très bien !\nNouvelle ligne"
    assert split_sentences(text) == ["Bonjour.", "Comment ça va ?", "Très bien !", "Nouvelle ligne"]


def test_first_chunk_is_a_single_sentence() -> None:
    chunks = chunk_text("Un. Deux. Trois. Quatre.")
    assert chunks[0] == "Un."
    assert chunks[1:] == ["Deux. Trois. Quatre."]


def test_long_sentence_is_split() -> None:
    sentence = "mot " * 200
    chunks = chunk_text(sentence, max_chars=50)
    assert all(len(c) <= 50 for c in chunks)
    assert " ".join(chunks).split() == sentence.split()


def test_empty_text_gives_no_chunks() -> None:
    assert chunk_text("  \n ") == []


# --- Bascule automatique ---


class FakeEngine(TTSEngine):
    """Faux moteur : simule une coupure réseau si offline=True."""

    def __init__(self, name: str, offline: bool = False, extension: str = ".mp3") -> None:
        self.name = name
        self.offline = offline
        self.extension = extension
        self.calls: list[Path | None] = []

    def synthesize(self, text, voice, rate="+0%", pitch="+0Hz", volume="+0%", output=None):
        if self.offline:
            raise TTSConnectionError("pas de réseau")
        self.calls.append(output)
        return output or Path(f"{self.name}{self.extension}")

    def list_voices(self) -> list[str]:
        if self.offline:
            raise TTSConnectionError("pas de réseau")
        return [self.name]


def test_fallback_uses_primary_when_online() -> None:
    engine = FallbackEngine(FakeEngine("edge"), FakeEngine("piper"), notify=lambda m: None)
    assert engine.synthesize("Bonjour", "fr-CA-AntoineNeural") == Path("edge.mp3")


def test_fallback_switches_to_backup_and_fixes_extension() -> None:
    messages: list[str] = []
    backup = FakeEngine("piper", extension=".wav")
    engine = FallbackEngine(FakeEngine("edge", offline=True), backup, notify=messages.append)

    result = engine.synthesize("Bonjour", "fr-CA-AntoineNeural", output=Path("a.mp3"))
    assert result == Path("a.wav")
    assert engine.offline and len(messages) == 1

    # Deuxième appel : directement sur le secours, sans nouveau message
    engine.synthesize("Encore", "fr-CA-AntoineNeural")
    assert len(messages) == 1 and len(backup.calls) == 2


def test_fallback_retries_primary_after_delay() -> None:
    primary = FakeEngine("edge", offline=True)
    engine = FallbackEngine(primary, FakeEngine("piper"), notify=lambda m: None, retry_after=0)
    engine.synthesize("Bonjour", "v")
    primary.offline = False  # le réseau revient
    assert engine.synthesize("Bonjour", "v") == Path("edge.mp3")


def test_fallback_does_not_hide_other_errors() -> None:
    class BadVoice(FakeEngine):
        def synthesize(self, *args, **kwargs):
            raise TTSError("voix inconnue")

    engine = FallbackEngine(BadVoice("edge"), FakeEngine("piper"), notify=lambda m: None)
    with pytest.raises(TTSError, match="voix inconnue"):
        engine.synthesize("Bonjour", "x")


# --- Piper (nécessite les modèles dans voices/) ---

needs_piper = pytest.mark.skipif(
    not (PIPER_VOICES_DIR / "fr_FR-siwis-medium.onnx").exists(),
    reason="modèle Piper non téléchargé",
)


def test_piper_maps_edge_voice_to_language() -> None:
    engine = PiperEngine()
    assert engine.resolve_voice("fr-CA-AntoineNeural") == "fr_FR-siwis-medium"
    assert engine.resolve_voice("en-GB-RyanNeural") == "en_US-lessac-medium"


def test_piper_invalid_rate() -> None:
    with pytest.raises(TTSError, match="Vitesse"):
        PiperEngine().synthesize("Bonjour", "fr", rate="vite")


@needs_piper
def test_piper_creates_wav(tmp_path: Path) -> None:
    out = PiperEngine().synthesize("Bonjour.", "fr-CA-AntoineNeural", output=tmp_path / "t.wav")
    assert out.exists() and out.stat().st_size > 1000
