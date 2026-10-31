"""Tests de la pause / reprise du Speaker (faux moteur, faux lecteur : pas de son)."""

import threading
import time
from pathlib import Path

import pytest

from tts import TTSEngine
from tts import player as real_player
from tts.speaker import Speaker


class RecordingEngine(TTSEngine):
    """Note chaque synthèse (texte + réglages) au lieu de produire de l'audio."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def synthesize(self, text, voice, rate="+0%", pitch="+0Hz", volume="+0%", output=None):
        self.calls.append((text, voice, rate))
        return output or Path("x.mp3")

    def list_voices(self) -> list[str]:
        return []


class FakePlayer:
    """Simule un son de `duration` secondes, avec pause / reprise."""

    def __init__(self, duration: float = 0.4) -> None:
        self.duration = duration
        self.end = 0.0
        self.remaining: float | None = None

    def start(self, path: Path) -> None:
        self.remaining = None
        self.end = time.monotonic() + self.duration

    def is_playing(self) -> bool:
        return self.remaining is None and time.monotonic() < self.end

    def pause(self) -> None:
        if self.remaining is None:
            self.remaining = max(0.0, self.end - time.monotonic())

    def unpause(self) -> None:
        if self.remaining is not None:
            self.end = time.monotonic() + self.remaining
            self.remaining = None

    def stop(self) -> None:
        self.end, self.remaining = 0.0, None


@pytest.fixture
def fake_player(monkeypatch: pytest.MonkeyPatch) -> FakePlayer:
    fake = FakePlayer()
    for name in ("start", "is_playing", "pause", "unpause", "stop"):
        monkeypatch.setattr(real_player, name, getattr(fake, name))
    return fake


def run_in_background(speaker: Speaker, text: str) -> threading.Thread:
    thread = threading.Thread(
        target=speaker.speak, args=(text, "fr-CA-AntoineNeural"), daemon=True
    )
    thread.start()
    time.sleep(0.15)  # on est en plein milieu de la première phrase
    return thread


def test_resume_without_changes_does_not_resynthesize(fake_player: FakePlayer) -> None:
    engine = RecordingEngine()
    speaker = Speaker(engine)
    thread = run_in_background(speaker, "Première phrase. Deuxième phrase.")

    speaker.pause()
    time.sleep(0.2)
    speaker.resume(voice="fr-CA-AntoineNeural", rate="+0%", pitch="+0Hz", volume="+0%")
    thread.join(timeout=5)

    assert [c[0] for c in engine.calls] == ["Première phrase.", "Deuxième phrase."]


def test_changed_settings_redo_current_sentence(fake_player: FakePlayer) -> None:
    engine = RecordingEngine()
    speaker = Speaker(engine)
    thread = run_in_background(speaker, "Première phrase. Deuxième phrase.")

    speaker.pause()
    speaker.resume(voice="fr-FR-HenriNeural", rate="+20%", pitch="+0Hz", volume="+0%")
    thread.join(timeout=5)

    new = ("fr-FR-HenriNeural", "+20%")
    # La phrase en cours est refaite avec les nouveaux réglages, et la suite aussi
    assert ("Première phrase.", *new) in engine.calls
    last_second = [c for c in engine.calls if c[0] == "Deuxième phrase."][-1]
    assert last_second == ("Deuxième phrase.", *new)


def test_stop_while_paused_ends_reading(fake_player: FakePlayer) -> None:
    speaker = Speaker(RecordingEngine())
    thread = run_in_background(speaker, "Une. Deux. Trois.")
    speaker.pause()
    speaker.stop()
    thread.join(timeout=2)
    assert not thread.is_alive()
