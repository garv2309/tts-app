"""Interface commune à tous les moteurs de synthèse vocale."""

from abc import ABC, abstractmethod
from pathlib import Path


class TTSError(Exception):
    """Erreur de synthèse, avec un message lisible pour l'utilisateur."""


class TTSConnectionError(TTSError):
    """Le service en ligne est injoignable (sert à déclencher le mode hors ligne)."""


class TTSEngine(ABC):
    """Classe de base : chaque moteur (edge-tts, Piper...) implémente ces méthodes."""

    # Format des fichiers produits (edge-tts : mp3, Piper : wav)
    extension: str = ".mp3"

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        output: Path | None = None,
    ) -> Path:
        """Convertit le texte en fichier audio et renvoie son chemin."""

    @abstractmethod
    def list_voices(self) -> list[str]:
        """Renvoie la liste des noms de voix disponibles."""
