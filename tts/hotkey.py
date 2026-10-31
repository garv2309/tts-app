"""Raccourci clavier global : fonctionne même quand la fenêtre n'a pas le focus."""

from collections.abc import Callable

import pyperclip
from pynput import keyboard


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
    listener = keyboard.GlobalHotKeys({hotkey: callback})
    listener.daemon = True
    listener.start()
    return listener
