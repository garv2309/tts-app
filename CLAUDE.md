# CLAUDE.md

## Le projet

Application Python de **synthèse vocale (text-to-speech)** : l'utilisateur donne du texte, l'application le lit à voix haute avec une **voix naturelle et fluide**, dans l'esprit des assistants vocaux modernes (style JARVIS, Siri) : posée, claire, agréable à écouter, pas robotique.

Langue principale : **français** (priorité aux voix québécoises `fr-CA`, avec `fr-FR` en option). L'anglais doit aussi fonctionner.

## Objectifs

1. Lire à voix haute n'importe quel texte saisi ou collé.
2. Voix neuronales naturelles (pas les voix système robotiques type `pyttsx3`).
3. Choix de la voix, de la vitesse, du ton et du volume.
4. Possibilité d'enregistrer l'audio en `.mp3`.
5. Interface simple : d'abord en ligne de commande, ensuite une interface graphique.

## Stack technique

- **Python 3.10+**
- **Moteur TTS principal : `edge-tts`** (voix neuronales Microsoft, gratuit, sans clé API, nécessite Internet)
  - Voix recommandées : `fr-CA-AntoineNeural`, `fr-CA-JeanNeural`, `fr-CA-ThierryNeural`, `fr-CA-SylvieNeural`, `fr-FR-HenriNeural`, `fr-FR-DeniseNeural`, `fr-FR-VivienneMultilingualNeural`, `fr-CH-ArianeNeural`, `en-US-GuyNeural`, `en-GB-RyanNeural`, `en-US-JennyNeural`
- **Moteur hors ligne (fallback) : `piper-tts`**, utilisé quand il n'y a pas de connexion
- **Lecture audio : `pygame`** (lecture des mp3, compatible Windows/macOS/Linux)
- **Interface graphique (phase 2) : `customtkinter`**
- Gestion des dépendances : **`uv`** (`pyproject.toml` + `uv.lock`, environnement `.venv` géré par uv)
- Lecture audio via `pygame-ce` (même API que `pygame`, qui n'a pas de wheel pour Python 3.14)

Ne pas utiliser `pyttsx3` ni `gTTS` comme moteur principal (voix trop robotiques).

## Architecture

```
tts-app/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── main.py              # Point d'entrée (CLI)
├── gui.py               # Interface graphique (phase 2)
├── tts/
│   ├── __init__.py
│   ├── base.py          # Classe abstraite TTSEngine
│   ├── edge_engine.py   # Implémentation edge-tts
│   ├── piper_engine.py  # Implémentation Piper (hors ligne)
│   ├── fallback.py      # Bascule automatique edge-tts → Piper sans Internet
│   ├── text_utils.py    # Découpage du texte en phrases / morceaux
│   ├── file_reader.py   # Extraction du texte des fichiers (txt, md, pdf, docx)
│   ├── speaker.py       # Lecture par morceaux (synthèse du suivant pendant la lecture)
│   ├── hotkey.py        # Raccourci clavier global + presse-papiers
│   └── player.py        # Lecture audio
├── config.py            # Voix par défaut, vitesse, dossier de sortie, raccourci
├── voices/              # Modèles Piper .onnx (ignoré par git)
├── output/              # Fichiers audio générés (ignoré par git)
└── tests/
    └── test_engines.py
```

- Chaque moteur hérite de `TTSEngine` avec les méthodes `synthesize(text, voice, rate, pitch) -> Path` et `list_voices() -> list[str]`.
- La lecture audio est séparée de la synthèse (`player.py`).
- `edge-tts` est asynchrone : encapsuler les appels avec `asyncio.run()` dans le moteur pour que le reste du code reste synchrone.

## Fonctionnalités par phase

**Phase 1 — CLI**
- `python main.py "Bonjour, je suis votre assistant."` lit le texte
- Options : `--voice`, `--rate` (ex. `+10%`), `--pitch`, `--save fichier.mp3`, `--list-voices`, `--file texte.txt`
- Mode interactif si aucun texte n'est donné (boucle : saisir → lire, `quit` pour sortir)

**Phase 2 — Interface graphique**
- Zone de texte, menu déroulant des voix, curseurs vitesse/ton, boutons Lire / Stop / Enregistrer
- La synthèse tourne dans un thread séparé pour ne pas figer l'interface

**Phase 3 — Bonus**
- Découpage des longs textes en phrases pour commencer la lecture plus vite
- Bascule automatique vers Piper si pas d'Internet
- Raccourci clavier global pour lire le texte du presse-papiers

## Conventions de code

- Code et noms de variables en **anglais**, commentaires et messages utilisateur en **français**
- Respecter PEP 8, type hints partout, docstrings courtes
- Gérer proprement les erreurs (pas de connexion, voix inexistante, texte vide) avec des messages clairs en français
- Pas de clés API ni de secrets dans le code

## Commandes

```bash
# Installer / mettre à jour l'environnement
uv sync

# Ajouter une dépendance
uv add nom-du-paquet

# Télécharger les voix Piper (hors ligne)
uv run python -m piper.download_voices fr_FR-siwis-medium en_US-lessac-medium --data-dir voices

# Lancer
uv run main.py "Texte à lire"
uv run main.py --hotkey          # Ctrl+Alt+L lit le presse-papiers
uv run main.py --list-voices
uv run gui.py

# Tests
uv run pytest
```

## Règles pour Claude

- Avancer phase par phase ; vérifier que la phase 1 fonctionne avant de passer à la suite.
- Après chaque changement, lancer le programme ou les tests pour vérifier.
- Expliquer brièvement les choix techniques (je suis étudiant, je veux comprendre le code).
- Garder le code simple et lisible plutôt que trop abstrait.
- Ne pas cloner ni imiter la voix d'une personne réelle ou d'un personnage existant : on vise un *style* naturel avec les voix fournies par les moteurs.
