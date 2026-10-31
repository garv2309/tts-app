"""Paramètres par défaut de l'application."""

import sys
import tempfile
from pathlib import Path

# Dans un exécutable PyInstaller, les fichiers embarqués (voix Piper…) sont dans sys._MEIPASS,
# un dossier interne à l'appli : on y lit, mais on n'y écrit pas (lecture seule sur Mac).
FROZEN: bool = getattr(sys, "frozen", False)
APP_DIR: Path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))

# Voix québécoise masculine, posée et claire
DEFAULT_VOICE: str = "fr-CA-AntoineNeural"

# Format attendu par edge-tts : pourcentage signé pour la vitesse/le volume, Hz pour le ton
DEFAULT_RATE: str = "+0%"
DEFAULT_PITCH: str = "+0Hz"
DEFAULT_VOLUME: str = "+0%"

# Dossier où sont écrits les fichiers audio générés (dossier temporaire du système dans l'exécutable)
OUTPUT_DIR: Path = (
    Path(tempfile.gettempdir()) / "lecteur-vocal" if FROZEN else Path(__file__).parent / "output"
)

# --- Piper (hors ligne) ---
# Modèles téléchargés avec : uv run python -m piper.download_voices <voix> --data-dir voices
PIPER_VOICES_DIR: Path = APP_DIR / "voices"
# Voix Piper utilisée selon la langue de la voix edge-tts demandée (fr-CA-... → "fr")
PIPER_VOICE_BY_LANG: dict[str, str] = {
    "fr": "fr_FR-siwis-medium",
    "en": "en_US-lessac-medium",
}
PIPER_DEFAULT_VOICE: str = "fr_FR-siwis-medium"

# Après une coupure réseau, on reste sur Piper ce nombre de secondes avant de réessayer edge-tts
OFFLINE_RETRY_SECONDS: float = 60.0

# --- Lecture par morceaux ---
# Taille maximale d'un morceau (les phrases courtes sont regroupées jusqu'à cette limite).
# Petit = reprise plus précise après un changement de réglage pendant une pause.
CHUNK_MAX_CHARS: int = 150

# --- Raccourci global (syntaxe pynput) : lit le presse-papiers, ou arrête la lecture ---
HOTKEY: str = "<ctrl>+<alt>+l"

# Voix proposées dans le menu de l'interface (toutes les voix restent utilisables avec --voice)
RECOMMENDED_VOICES: list[str] = [
    # Québec (Sylvie est la seule voix féminine fr-CA du service)
    "fr-CA-AntoineNeural",  # homme
    "fr-CA-JeanNeural",  # homme
    "fr-CA-ThierryNeural",  # homme
    "fr-CA-SylvieNeural",  # femme
    # France et Suisse
    "fr-FR-HenriNeural",  # homme
    "fr-FR-DeniseNeural",  # femme
    "fr-FR-VivienneMultilingualNeural",  # femme
    "fr-CH-ArianeNeural",  # femme
    # Anglais
    "en-US-GuyNeural",  # homme
    "en-GB-RyanNeural",  # homme
    "en-US-JennyNeural",  # femme
]
