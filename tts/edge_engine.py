"""Moteur edge-tts : voix neuronales Microsoft (nécessite Internet)."""

import asyncio
import re
from pathlib import Path

import aiohttp
import edge_tts
from edge_tts.exceptions import NoAudioReceived

from config import OUTPUT_DIR
from tts.base import TTSConnectionError, TTSEngine, TTSError

# Validation des réglages avant l'appel réseau, pour donner un message clair
_PERCENT_RE = re.compile(r"^[+-]\d+%$")
_HZ_RE = re.compile(r"^[+-]\d+Hz$")


class EdgeEngine(TTSEngine):
    """Synthèse via edge-tts. Les appels async sont encapsulés dans asyncio.run()."""

    def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        output: Path | None = None,
    ) -> Path:
        """Génère un mp3 à partir du texte et renvoie son chemin."""
        if not text.strip():
            raise TTSError("Le texte est vide : rien à lire.")
        if not _PERCENT_RE.match(rate):
            raise TTSError(f"Vitesse invalide « {rate} » (exemple : +10% ou -20%).")
        if not _HZ_RE.match(pitch):
            raise TTSError(f"Ton invalide « {pitch} » (exemple : +5Hz ou -10Hz).")
        if not _PERCENT_RE.match(volume):
            raise TTSError(f"Volume invalide « {volume} » (exemple : +20% ou -30%).")

        if output is None:
            OUTPUT_DIR.mkdir(exist_ok=True)
            output = OUTPUT_DIR / "last.mp3"
        else:
            output.parent.mkdir(parents=True, exist_ok=True)

        try:
            communicate = edge_tts.Communicate(
                text, voice, rate=rate, pitch=pitch, volume=volume
            )
            asyncio.run(communicate.save(str(output)))
        except ValueError:
            # edge-tts lève ValueError si le nom de voix est mal formé
            raise TTSError(
                f"Voix « {voice} » invalide. Utilisez --list-voices pour voir les choix."
            ) from None
        except NoAudioReceived:
            # Nom bien formé mais voix inconnue du service
            raise TTSError(
                f"Aucun audio reçu : la voix « {voice} » n'existe probablement pas."
            ) from None
        except (aiohttp.ClientError, OSError) as exc:
            raise TTSConnectionError(
                f"Impossible de joindre le service vocal. Vérifiez votre connexion Internet. ({exc})"
            ) from None
        return output

    def list_voices(self) -> list[str]:
        """Renvoie les voix disponibles, triées par nom."""
        try:
            voices = asyncio.run(edge_tts.list_voices())
        except (aiohttp.ClientError, OSError) as exc:
            raise TTSConnectionError(
                f"Impossible de récupérer la liste des voix. Vérifiez votre connexion Internet. ({exc})"
            ) from None
        return sorted(v["ShortName"] for v in voices)
