"""Journal des erreurs : toute exception non gérée est écrite dans un fichier lisible.

Une application fenêtrée n'a pas de console : sans ce fichier, une erreur passe inaperçue.
"""

import faulthandler
import logging
import platform
import sys
import tempfile
import threading
import tkinter
from pathlib import Path
from types import TracebackType

LOG_NAME = "LecteurVocal.log"

logger = logging.getLogger("lecteur_vocal")

# Nombre d'exceptions non gérées depuis le démarrage (utilisé par --selftest)
error_count: int = 0


def log_path() -> Path:
    """Mac : ~/Library/Logs (visible dans l'app Console). Ailleurs : à côté de l'exécutable."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / LOG_NAME
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / LOG_NAME
    return Path(__file__).parent.parent / LOG_NAME


def _open_log_file(path: Path):  # noqa: ANN202
    """Ouvre le fichier en ajout ; dossier protégé en écriture → dossier temporaire."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.open("a", encoding="utf-8")
    except OSError:
        return (Path(tempfile.gettempdir()) / LOG_NAME).open("a", encoding="utf-8")


def _record(
    where: str,
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    global error_count
    error_count += 1
    logger.error("Exception non gérée (%s)", where, exc_info=(exc_type, exc, tb))


def install() -> Path:
    """Branche le journal sur toutes les sources d'exceptions non gérées et renvoie son chemin."""
    log_file = _open_log_file(log_path())
    handler = logging.StreamHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # 1. Exceptions du thread principal (ex. au démarrage)
    sys.excepthook = lambda t, e, tb: _record("thread principal", t, e, tb)
    # 2. Exceptions dans les threads de fond (synthèse, ouverture de fichier…)
    threading.excepthook = lambda a: _record(
        f"thread {a.thread.name if a.thread else '?'}", a.exc_type, a.exc_value, a.exc_traceback
    )
    # 3. Exceptions dans les callbacks Tk (boutons, after…) : Tk les attrape lui-même
    #    et les afficherait seulement sur la console, absente dans l'exécutable
    tkinter.Tk.report_callback_exception = lambda self, t, e, tb: _record("interface", t, e, tb)
    # 4. Plantages natifs (segfault…) : faulthandler écrit la pile Python avant de mourir
    faulthandler.enable(log_file, all_threads=True)

    logger.info(
        "Démarrage : Python %s, %s %s (%s)",
        platform.python_version(),
        platform.system(),
        platform.mac_ver()[0] or platform.release(),
        platform.machine(),
    )
    return Path(log_file.name)
