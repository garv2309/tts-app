"""Raccourci clavier global : fonctionne même quand la fenêtre n'a pas le focus."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

import pyperclip

if TYPE_CHECKING:
    from pynput import keyboard

# Sur macOS 14+, le listener de pynput lit la disposition du clavier (TSMGetInputSourceProperty)
# depuis son thread : macOS l'interdit hors du thread principal et tue l'application.
# On n'utilise donc le raccourci global que sur Windows et Linux.
GLOBAL_HOTKEY_SUPPORTED: bool = sys.platform != "darwin"


def read_clipboard() -> str:
    """Renvoie le texte du presse-papiers (chaîne vide s'il n'y a pas de texte)."""
    try:
        return pyperclip.paste() or ""
    except pyperclip.PyperclipException:
        return ""


def start_listener(hotkey: str, callback: Callable[[], None]) -> keyboard.GlobalHotKeys:
    """Écoute le raccourci dans un thread de fond et appelle callback à chaque appui.

    Attention : callback s'exécute dans le thread de pynput, il doit rester rapide.
    """
    if not GLOBAL_HOTKEY_SUPPORTED:
        raise RuntimeError("Le raccourci global n'est pas disponible sur macOS.")
    # Import ici : pynput n'est installé que là où le raccourci global est utilisé (pas sur Mac)
    from pynput import keyboard

    listener = keyboard.GlobalHotKeys({hotkey: callback})
    listener.daemon = True
    listener.start()
    return listener
