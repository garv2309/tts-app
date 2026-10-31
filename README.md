# tts-app

Lecture de texte à voix haute avec des voix neuronales (edge-tts), et une voix hors ligne
(Piper) qui prend le relais automatiquement quand Internet est coupé.

Pour comprendre le code en détail : voir [EXPLICATION.md](EXPLICATION.md).

## Installation

Nécessite [uv](https://docs.astral.sh/uv/).

```bash
uv sync
# Voix hors ligne (≈ 60 Mo chacune)
uv run python -m piper.download_voices fr_FR-siwis-medium en_US-lessac-medium --data-dir voices
```

## Interface graphique

```bash
uv run gui.py
```

**⏸ Pause** fige la lecture. Pendant la pause, vous pouvez changer la voix, la vitesse, le ton ou
le volume : à la reprise, la phrase en cours est relue depuis son début avec les nouveaux réglages.
Sans changement, la lecture reprend exactement où elle était.

Copiez du texte n'importe où puis appuyez sur **Ctrl+Alt+L** : il est collé dans la fenêtre et lu.
Un deuxième appui arrête la lecture.

## Ligne de commande

```bash
uv run main.py "Bonjour, je suis votre assistant."
uv run main.py "Hello there" --voice en-GB-RyanNeural
uv run main.py "Plus vite" --rate=+20% --pitch=-5Hz
uv run main.py --file texte.txt --save output/lecture.mp3
uv run main.py --list-voices
uv run main.py --offline "Toujours la voix Piper"
uv run main.py --hotkey            # attend Ctrl+Alt+L en arrière-plan
uv run main.py                     # mode interactif, 'quit' pour sortir
```

Les longs textes sont lus phrase par phrase : la lecture commence dès que la première phrase est prête.

## Exécutable à partager (Windows / macOS)

L'appli graphique est empaquetée avec [PyInstaller](https://pyinstaller.org) : Python, les
bibliothèques et les voix Piper sont inclus, vos amis n'ont rien à installer.

**Sur Windows (votre PC)** :

```bash
uv run pyinstaller lecteur_vocal.spec --noconfirm
```

Résultat : le dossier `dist/LecteurVocal/` (≈ 280 Mo). Zippez **tout le dossier** et partagez-le ;
on lance `LecteurVocal.exe`. Au premier lancement, Windows SmartScreen peut afficher « Windows a
protégé votre ordinateur » (appli non signée) : cliquer sur **Informations complémentaires →
Exécuter quand même**.

**Pour macOS** : PyInstaller ne peut construire que pour le système sur lequel il tourne. Le
workflow `.github/workflows/build.yml` construit les deux versions sur les serveurs de GitHub :
poussez le projet sur GitHub, puis **Actions → Build → Run workflow**, et téléchargez les zips
dans la section *Artifacts*. (Sur un Mac, `uv sync` puis la même commande PyInstaller marche aussi.)

Sur Mac, l'appli n'est pas signée par Apple : la première fois, **clic droit sur l'app → Ouvrir →
Ouvrir**. Si macOS dit que l'app « est endommagée », lancer dans le Terminal :
`xattr -cr /chemin/vers/LecteurVocal.app`. Pour le raccourci global, autoriser l'app dans
**Réglages Système → Confidentialité et sécurité → Accessibilité**.

## Tests

```bash
uv run pytest                     # tous les tests
uv run pytest -m "not network"    # sans Internet
```
