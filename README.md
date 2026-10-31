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

**📂 Ouvrir** charge le texte d'un fichier `.txt`, `.md`, `.pdf` ou `.docx` (Word) dans la zone de
texte ; on peut le relire ou le modifier avant de cliquer sur **▶ Lire**. Les PDF scannés (images
sans texte sélectionnable) ne peuvent pas être lus.

Copiez du texte n'importe où puis appuyez sur **Ctrl+Alt+L** : il est collé dans la fenêtre et lu.
Un deuxième appui arrête la lecture.

## Ligne de commande

```bash
uv run main.py "Bonjour, je suis votre assistant."
uv run main.py "Hello there" --voice en-GB-RyanNeural
uv run main.py "Plus vite" --rate=+20% --pitch=-5Hz
uv run main.py --file texte.txt --save output/lecture.mp3
uv run main.py --file cours.pdf    # aussi .md et .docx
uv run main.py --list-voices
uv run main.py --offline "Toujours la voix Piper"
uv run main.py --hotkey            # attend Ctrl+Alt+L en arrière-plan (Windows/Linux)
uv run gui.py --selftest           # ouvre la fenêtre 5 s puis quitte (code 0 = OK)
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
Chaque appli construite est lancée avec `--selftest` : si elle plante, le workflow échoue.

**Publier une version (lien fixe pour les amis)** : pousser un tag, par exemple
`git tag v0.2.0 && git push origin v0.2.0`. Les zips sont publiés dans une GitHub Release, et ces
liens pointent toujours vers la dernière version :

- macOS : https://github.com/garv2309/tts-app/releases/latest/download/LecteurVocal-macOS.zip
- Windows : https://github.com/garv2309/tts-app/releases/latest/download/LecteurVocal-Windows.zip

(Le dépôt doit être public pour que les amis puissent télécharger sans compte.)

Sur Mac, l'appli n'est pas signée par Apple : la première fois, **clic droit sur l'app → Ouvrir →
Ouvrir**. Si macOS dit que l'app « est endommagée », lancer dans le Terminal :
`xattr -cr /chemin/vers/LecteurVocal.app`. Sur Mac, pas de raccourci global (macOS 14+ fait
planter pynput) : appuyer sur **⌘L** dans la fenêtre pour lire le presse-papiers.

**En cas de problème**, les erreurs sont écrites dans un fichier log :
`~/Library/Logs/LecteurVocal.log` sur Mac, `LecteurVocal.log` à côté de `LecteurVocal.exe` sur Windows.

## Tests

```bash
uv run pytest                     # tous les tests
uv run pytest -m "not network"    # sans Internet
```
