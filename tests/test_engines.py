"""Tests du moteur edge-tts."""

import pytest

from config import RECOMMENDED_VOICES
from tts import EdgeEngine, TTSError


@pytest.fixture
def engine() -> EdgeEngine:
    return EdgeEngine()


# --- Validation locale (pas besoin d'Internet) ---

def test_empty_text_raises(engine: EdgeEngine) -> None:
    with pytest.raises(TTSError, match="vide"):
        engine.synthesize("   ", "fr-CA-AntoineNeural")


@pytest.mark.parametrize("rate", ["10%", "+10", "vite"])
def test_invalid_rate_raises(engine: EdgeEngine, rate: str) -> None:
    with pytest.raises(TTSError, match="Vitesse"):
        engine.synthesize("Bonjour", "fr-CA-AntoineNeural", rate=rate)


def test_invalid_pitch_raises(engine: EdgeEngine) -> None:
    with pytest.raises(TTSError, match="Ton"):
        engine.synthesize("Bonjour", "fr-CA-AntoineNeural", pitch="+5")


# --- Tests réseau ---

@pytest.mark.network
def test_synthesize_creates_mp3(engine: EdgeEngine, tmp_path) -> None:
    out = engine.synthesize("Bonjour.", "fr-CA-AntoineNeural", output=tmp_path / "t.mp3")
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.network
def test_list_voices_contains_french(engine: EdgeEngine) -> None:
    assert "fr-CA-AntoineNeural" in engine.list_voices()


@pytest.mark.network
def test_recommended_voices_exist(engine: EdgeEngine) -> None:
    # Protège contre une faute de frappe dans la liste du menu de l'interface
    missing = set(RECOMMENDED_VOICES) - set(engine.list_voices())
    assert not missing


@pytest.mark.network
def test_unknown_voice_raises(engine: EdgeEngine) -> None:
    with pytest.raises(TTSError):
        engine.synthesize("Bonjour", "xx-XX-NobodyNeural")
