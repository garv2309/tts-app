"""Lecture des fichiers audio avec pygame."""

import os
import time
from pathlib import Path

# Masque le message de bienvenue que pygame affiche à l'import
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402


def start(path: Path) -> None:
    """Démarre la lecture sans attendre la fin (utile pour l'interface graphique)."""
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    stop()
    pygame.mixer.music.load(str(path))
    pygame.mixer.music.play()


def is_playing() -> bool:
    """Indique si un son est en cours de lecture."""
    return bool(pygame.mixer.get_init()) and pygame.mixer.music.get_busy()


def pause() -> None:
    """Met la lecture en pause (on peut reprendre au même endroit avec unpause)."""
    if pygame.mixer.get_init():
        pygame.mixer.music.pause()


def unpause() -> None:
    """Reprend la lecture là où elle était."""
    if pygame.mixer.get_init():
        pygame.mixer.music.unpause()


def stop() -> None:
    """Arrête la lecture et libère le fichier (sous Windows il resterait verrouillé)."""
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()


def play(path: Path) -> None:
    """Lit un fichier audio et attend la fin de la lecture (Ctrl+C pour arrêter)."""
    start(path)
    try:
        while is_playing():
            time.sleep(0.1)
    finally:
        stop()
