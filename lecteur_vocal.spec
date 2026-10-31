# Recette PyInstaller : construit l'application graphique en exécutable.
#   Windows : dist/LecteurVocal/LecteurVocal.exe
#   macOS   : dist/LecteurVocal.app
# Lancer avec : uv run pyinstaller lecteur_vocal.spec --noconfirm
# PyInstaller ne fait pas de compilation croisée : construire sur chaque système.

import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

APP_NAME = "LecteurVocal"

# Piper a besoin de ses données espeak-ng (prononciation) et de sa bibliothèque native.
# On ignore piper.train (entraînement de voix), inutile et très lourd.
piper_datas = collect_data_files("piper", excludes=["train/**"])
piper_binaries = collect_dynamic_libs("piper")

a = Analysis(
    ["gui.py"],
    binaries=piper_binaries,
    datas=[
        # Voix hors ligne : copiées dans le dossier « voices » de l'appli
        ("voices/*.onnx", "voices"),
        ("voices/*.onnx.json", "voices"),
        *piper_datas,
        # Thèmes et polices de customtkinter
        *collect_data_files("customtkinter"),
    ],
    # pynput choisit son backend (Windows, macOS, Linux) à l'exécution : PyInstaller ne le voit pas
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32"]
    if sys.platform == "win32"
    else ["pynput.keyboard._darwin", "pynput.mouse._darwin"],
    excludes=["piper.train", "pytest", "torch"],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # mode « dossier » : démarrage rapide, rien à décompresser
    name=APP_NAME,
    console=False,  # pas de fenêtre noire de terminal
    # Mac : puces Apple (M1/M2/M3). Windows : None = architecture du Python utilisé (inchangé)
    target_arch="arm64" if sys.platform == "darwin" else None,
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="ca.lecteurvocal.app",
        info_plist={
            "CFBundleDisplayName": "Lecteur vocal",
            "NSHighResolutionCapable": True,
        },
    )
