"""Lecture d'un texte morceau par morceau : on synthétise la suite pendant qu'on joue."""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import OUTPUT_DIR
from tts import player
from tts.base import TTSEngine
from tts.text_utils import chunk_text

Settings = dict[str, str]


class Speaker:
    """Lit un texte long sans attendre que tout soit synthétisé.

    pause(), resume() et stop() peuvent être appelés depuis un autre thread (ex. l'interface).
    """

    def __init__(self, engine: TTSEngine) -> None:
        self.engine = engine
        self._stop_event = threading.Event()
        # Événement « activé » = pas en pause ; le thread de lecture attend dessus pendant la pause
        self._running = threading.Event()
        self._running.set()
        # Réglages courants (voice, rate, pitch, volume), modifiables pendant une pause
        self._lock = threading.Lock()
        self._settings: Settings = {}
        # Augmente à chaque changement de réglages : un morceau fait avec une ancienne
        # version est périmé, même si le changement a été très rapide
        self._version = 0

    # --- Contrôles ---

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    def pause(self) -> None:
        """Met la lecture en pause."""
        # L'ordre compte : marquer la pause AVANT de figer l'audio (voir _play)
        self._running.clear()
        player.pause()

    def resume(self, **settings: str) -> None:
        """Reprend la lecture. Si les réglages ont changé, la phrase en cours est refaite avec."""
        with self._lock:
            changed = any(self._settings.get(k) != v for k, v in settings.items())
            if changed:
                self._settings.update(settings)
                self._version += 1
        if not changed:
            # Rien n'a changé : on repart exactement où on était
            player.unpause()
        self._running.set()

    def stop(self) -> None:
        """Demande l'arrêt de la lecture en cours."""
        self._stop_event.set()
        self._running.set()
        player.stop()

    # --- Lecture ---

    def speak(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Lit le texte (bloquant). on_progress(i, total) est appelé avant chaque morceau."""
        self._stop_event.clear()
        self._running.set()
        with self._lock:
            self._settings = {"voice": voice, "rate": rate, "pitch": pitch, "volume": volume}

        chunks = chunk_text(text)
        if not chunks:
            # Laisse le moteur produire son message « texte vide »
            self.engine.synthesize(text, voice, rate, pitch, volume)
            return

        OUTPUT_DIR.mkdir(exist_ok=True)

        def synth(index: int) -> tuple[Path, int]:
            # Deux fichiers en alternance : l'un joue pendant que l'autre s'écrit
            with self._lock:
                settings, version = dict(self._settings), self._version
            path = OUTPUT_DIR / f"chunk_{index % 2}{self.engine.extension}"
            return self.engine.synthesize(chunks[index], output=path, **settings), version

        # Un seul thread de synthèse, qui a toujours un morceau d'avance sur la lecture
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(synth, 0)
            i = 0
            while i < len(chunks):
                path, version = future.result()  # relance l'erreur de synthèse s'il y en a eu une
                if not self._wait_while_paused():
                    break
                if version != self._version:
                    # Préparé avec d'anciens réglages : on le refait
                    future = pool.submit(synth, i)
                    continue
                if i + 1 < len(chunks):
                    future = pool.submit(synth, i + 1)
                if on_progress:
                    on_progress(i + 1, len(chunks))

                finished = self._play(path, version)
                # Libère le fichier avant qu'il soit réécrit
                player.stop()
                if self._stop_event.is_set():
                    break
                if finished:
                    i += 1
                else:
                    # Réglages changés pendant la pause : on refait la même phrase
                    future = pool.submit(synth, i)

    def _play(self, path: Path, version: int) -> bool:
        """Joue un morceau. Renvoie False s'il faut le refaire avec de nouveaux réglages."""
        player.start(path)
        while not self._stop_event.is_set():
            if self.paused:
                # Si la pause est arrivée juste entre deux morceaux, l'audio a pu démarrer
                player.pause()
                if not self._wait_while_paused():
                    return True  # arrêt demandé pendant la pause
                continue
            if self._version != version:
                return False
            if not player.is_playing():
                # La musique peut sembler arrêtée juste parce qu'on vient de mettre en pause :
                # comme pause() marque la pause avant de figer l'audio, on revérifie ici
                if self.paused:
                    continue
                return True
            self._stop_event.wait(0.05)
        return True

    def _wait_while_paused(self) -> bool:
        """Attend la fin de la pause. Renvoie False si un arrêt a été demandé."""
        while not self._running.wait(0.05):
            if self._stop_event.is_set():
                return False
        return not self._stop_event.is_set()
