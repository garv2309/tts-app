"""Moteur Piper : synthèse locale, fonctionne sans Internet."""

import re
import wave
from pathlib import Path

from config import OUTPUT_DIR, PIPER_DEFAULT_VOICE, PIPER_VOICE_BY_LANG, PIPER_VOICES_DIR
from tts.base import TTSEngine, TTSError

_PERCENT_RE = re.compile(r"^([+-]\d+)%$")


def _percent(value: str, name: str) -> int:
    """Convertit « +10% » en 10, avec un message clair si le format est faux."""
    match = _PERCENT_RE.match(value)
    if not match:
        raise TTSError(f"{name} invalide « {value} » (exemple : +10% ou -20%).")
    return int(match.group(1))


class PiperEngine(TTSEngine):
    """Synthèse via Piper. Le ton (pitch) n'est pas réglable avec ce moteur."""

    extension = ".wav"

    def __init__(self, voices_dir: Path = PIPER_VOICES_DIR) -> None:
        self.voices_dir = voices_dir
        # Charger un modèle prend environ une seconde : on garde ceux déjà chargés
        self._loaded: dict[str, "PiperVoice"] = {}  # noqa: F821

    def resolve_voice(self, voice: str) -> str:
        """Accepte une voix Piper, ou une voix edge-tts dont on garde seulement la langue."""
        if (self.voices_dir / f"{voice}.onnx").exists():
            return voice
        lang = voice.split("-")[0].split("_")[0].lower()
        return PIPER_VOICE_BY_LANG.get(lang, PIPER_DEFAULT_VOICE)

    def _load(self, name: str) -> "PiperVoice":  # noqa: F821
        # Import ici : onnxruntime est lourd, inutile de le charger si on reste en ligne
        from piper import PiperVoice

        if name not in self._loaded:
            model = self.voices_dir / f"{name}.onnx"
            if not model.exists():
                raise TTSError(
                    f"Voix Piper « {name} » introuvable. Téléchargez-la avec :\n"
                    f"  uv run python -m piper.download_voices {name} --data-dir voices"
                )
            self._loaded[name] = PiperVoice.load(model)
        return self._loaded[name]

    def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        output: Path | None = None,
    ) -> Path:
        """Génère un wav à partir du texte et renvoie son chemin."""
        from piper import SynthesisConfig

        if not text.strip():
            raise TTSError("Le texte est vide : rien à lire.")
        rate_pct = _percent(rate, "Vitesse")
        volume_pct = _percent(volume, "Volume")

        if output is None:
            OUTPUT_DIR.mkdir(exist_ok=True)
            output = OUTPUT_DIR / "last.wav"
        else:
            output.parent.mkdir(parents=True, exist_ok=True)

        # length_scale = durée relative : plus petit = plus rapide (+100% → 0.5)
        config = SynthesisConfig(
            length_scale=1 / max(0.1, 1 + rate_pct / 100),
            volume=max(0.0, 1 + volume_pct / 100),
        )
        piper_voice = self._load(self.resolve_voice(voice))
        with wave.open(str(output), "wb") as wav_file:
            piper_voice.synthesize_wav(text, wav_file, syn_config=config)
        return output

    def list_voices(self) -> list[str]:
        """Renvoie les voix Piper présentes dans le dossier voices/."""
        return sorted(p.stem for p in self.voices_dir.glob("*.onnx"))
