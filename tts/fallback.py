"""Moteur qui bascule automatiquement vers Piper quand Internet est coupé."""

import time
from collections.abc import Callable
from pathlib import Path

from config import OFFLINE_RETRY_SECONDS
from tts.base import TTSConnectionError, TTSEngine


class FallbackEngine(TTSEngine):
    """Essaie le moteur principal ; en cas de coupure réseau, utilise le moteur de secours."""

    def __init__(
        self,
        primary: TTSEngine,
        backup: TTSEngine,
        notify: Callable[[str], None] = print,
        retry_after: float = OFFLINE_RETRY_SECONDS,
    ) -> None:
        self.primary = primary
        self.backup = backup
        self.notify = notify
        self.retry_after = retry_after
        # Moment de la dernière coupure : évite d'attendre le réseau à chaque phrase
        self._offline_since: float | None = None

    @property
    def offline(self) -> bool:
        """Vrai si on est en mode hors ligne (coupure récente)."""
        if self._offline_since is None:
            return False
        if time.monotonic() - self._offline_since > self.retry_after:
            self._offline_since = None  # on retentera le moteur principal
            return False
        return True

    def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        output: Path | None = None,
    ) -> Path:
        """Synthétise avec le moteur principal, ou le secours s'il n'y a pas de réseau."""
        if not self.offline:
            try:
                return self.primary.synthesize(text, voice, rate, pitch, volume, output)
            except TTSConnectionError:
                self._offline_since = time.monotonic()
                self.notify("Pas de connexion Internet : bascule vers la voix hors ligne (Piper).")

        # Le moteur de secours produit peut-être un autre format (wav au lieu de mp3)
        if output is not None:
            output = output.with_suffix(self.backup.extension)
        return self.backup.synthesize(text, voice, rate, pitch, volume, output)

    @property
    def extension(self) -> str:  # type: ignore[override]
        return self.backup.extension if self.offline else self.primary.extension

    def list_voices(self) -> list[str]:
        """Voix du moteur principal, ou du secours si hors ligne."""
        if not self.offline:
            try:
                return self.primary.list_voices()
            except TTSConnectionError:
                self._offline_since = time.monotonic()
                self.notify("Pas de connexion Internet : voici les voix hors ligne (Piper).")
        return self.backup.list_voices()
