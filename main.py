"""Point d'entrée en ligne de commande."""

import argparse
import sys
import threading
from pathlib import Path

from config import DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE, DEFAULT_VOLUME, HOTKEY
from tts import PiperEngine, TTSEngine, TTSError, create_engine
from tts.hotkey import read_clipboard, start_listener
from tts.player import play
from tts.speaker import Speaker


def parse_args() -> argparse.Namespace:
    """Définit et lit les options de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Lit du texte à voix haute.")
    parser.add_argument("text", nargs="?", help="Texte à lire (sinon mode interactif)")
    parser.add_argument("--file", type=Path, help="Fichier texte à lire")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Nom de la voix")
    # Valeurs négatives : écrire --rate=-10% (sinon argparse croit à une option)
    parser.add_argument("--rate", default=DEFAULT_RATE, help="Vitesse, ex. +10%% ou --rate=-10%%")
    parser.add_argument("--pitch", default=DEFAULT_PITCH, help="Ton, ex. +5Hz ou --pitch=-5Hz")
    parser.add_argument("--volume", default=DEFAULT_VOLUME, help="Volume, ex. +20%%")
    parser.add_argument("--save", type=Path, help="Enregistre l'audio dans ce fichier .mp3")
    parser.add_argument("--list-voices", action="store_true", help="Affiche les voix disponibles")
    parser.add_argument("--offline", action="store_true", help="Force la voix hors ligne (Piper)")
    parser.add_argument(
        "--hotkey", action="store_true", help=f"Reste en attente : {HOTKEY} lit le presse-papiers"
    )
    return parser.parse_args()


def speak(engine: TTSEngine, speaker: Speaker, text: str, args: argparse.Namespace) -> None:
    """Lit le texte ; avec --save, produit d'abord un seul fichier complet."""
    if args.save:
        path = engine.synthesize(text, args.voice, args.rate, args.pitch, args.volume, args.save)
        print(f"Audio enregistré dans {path}")
        play(path)
    else:
        speaker.speak(text, args.voice, args.rate, args.pitch, args.volume)


def interactive(engine: TTSEngine, speaker: Speaker, args: argparse.Namespace) -> None:
    """Boucle : saisir un texte, l'entendre ; 'quit' pour sortir."""
    print(f"Mode interactif (voix : {args.voice}). Tapez 'quit' pour sortir.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in {"quit", "exit", "q"}:
            break
        if not text:
            continue
        try:
            speak(engine, speaker, text, args)
        except TTSError as exc:
            print(f"Erreur : {exc}")
        except KeyboardInterrupt:
            speaker.stop()
            print("\nLecture interrompue.")


def hotkey_mode(speaker: Speaker, args: argparse.Namespace) -> None:
    """Attend le raccourci global : lit le presse-papiers, ou arrête la lecture en cours."""
    current: threading.Thread | None = None

    def read_aloud(text: str) -> None:
        try:
            speaker.speak(text, args.voice, args.rate, args.pitch, args.volume)
        except TTSError as exc:
            print(f"Erreur : {exc}")

    def on_hotkey() -> None:
        nonlocal current
        # Deuxième appui pendant la lecture = Stop
        if current and current.is_alive():
            speaker.stop()
            return
        text = read_clipboard().strip()
        if not text:
            print("Le presse-papiers ne contient pas de texte.")
            return
        print(f"Lecture : {text[:60]}{'…' if len(text) > 60 else ''}")
        # Thread séparé : le callback de pynput doit rendre la main rapidement
        current = threading.Thread(target=read_aloud, args=(text,), daemon=True)
        current.start()

    listener = start_listener(HOTKEY, on_hotkey)
    print(f"Copiez du texte puis appuyez sur {HOTKEY} pour l'entendre (à nouveau pour arrêter).")
    print("Ctrl+C pour quitter.")
    try:
        # join() avec délai : sous Windows, un join() sans délai bloque Ctrl+C
        while listener.is_alive():
            listener.join(0.5)
    except KeyboardInterrupt:
        speaker.stop()
        print("\nAu revoir.")


def main() -> int:
    """Lance l'application et renvoie le code de sortie."""
    # La console Windows n'est pas toujours en UTF-8 : évite les erreurs sur les accents
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    engine: TTSEngine = PiperEngine() if args.offline else create_engine()
    speaker = Speaker(engine)

    try:
        if args.list_voices:
            for name in engine.list_voices():
                print(name)
            return 0

        if args.hotkey:
            hotkey_mode(speaker, args)
        elif args.file:
            try:
                text = args.file.read_text(encoding="utf-8")
            except OSError:
                print(f"Erreur : impossible de lire le fichier « {args.file} ».")
                return 1
            speak(engine, speaker, text, args)
        elif args.text is not None:
            speak(engine, speaker, args.text, args)
        else:
            interactive(engine, speaker, args)
    except TTSError as exc:
        print(f"Erreur : {exc}")
        return 1
    except KeyboardInterrupt:
        speaker.stop()
        print("\nLecture interrompue.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
