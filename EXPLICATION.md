# Comprendre le code de tts-app

Ce document explique **comment le projet fonctionne**, fichier par fichier, et surtout **pourquoi**
il est construit ainsi. Lis-le dans l'ordre : chaque partie s'appuie sur la précédente.

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Le chemin d'un texte, du clavier au haut-parleur](#2-le-chemin-dun-texte-du-clavier-au-haut-parleur)
3. [`config.py` : les réglages](#3-configpy--les-réglages)
4. [`tts/base.py` : le contrat commun des moteurs](#4-ttsbasepy--le-contrat-commun-des-moteurs)
5. [`tts/edge_engine.py` : la voix en ligne](#5-ttsedge_enginepy--la-voix-en-ligne)
6. [`tts/piper_engine.py` : la voix hors ligne](#6-ttspiper_enginepy--la-voix-hors-ligne)
7. [`tts/fallback.py` : la bascule automatique](#7-ttsfallbackpy--la-bascule-automatique)
8. [`tts/player.py` : jouer le son](#8-ttsplayerpy--jouer-le-son)
9. [`tts/text_utils.py` : découper le texte](#9-ttstext_utilspy--découper-le-texte)
10. [`tts/speaker.py` : le chef d'orchestre](#10-ttsspeakerpy--le-chef-dorchestre)
11. [`tts/hotkey.py` : le raccourci global](#11-ttshotkeypy--le-raccourci-global)
12. [`main.py` : la ligne de commande](#12-mainpy--la-ligne-de-commande)
13. [`gui.py` : l'interface graphique](#13-guipy--linterface-graphique)
14. [Les tests](#14-les-tests)
15. [uv et `pyproject.toml`](#15-uv-et-pyprojecttoml)
16. [Les concepts Python à retenir](#16-les-concepts-python-à-retenir)
17. [Exercices pour progresser](#17-exercices-pour-progresser)

---

## 1. Vue d'ensemble

```
tts-app/
├── main.py              ← point d'entrée en ligne de commande
├── gui.py               ← point d'entrée graphique
├── config.py            ← toutes les valeurs par défaut
├── tts/                 ← le « cœur » : ne sait rien de la CLI ni de la GUI
│   ├── base.py          ← classe abstraite TTSEngine + exceptions
│   ├── edge_engine.py   ← moteur en ligne (Microsoft, edge-tts)
│   ├── piper_engine.py  ← moteur hors ligne (Piper)
│   ├── fallback.py      ← choisit edge-tts ou Piper selon le réseau
│   ├── text_utils.py    ← découpe le texte en morceaux
│   ├── speaker.py       ← lit les morceaux un par un, gère pause/stop
│   ├── player.py        ← joue un fichier audio (pygame)
│   └── hotkey.py        ← raccourci clavier global + presse-papiers
├── tests/               ← tests automatiques (pytest)
├── voices/              ← modèles Piper téléchargés (.onnx)
└── output/              ← fichiers audio générés
```

**L'idée principale : séparer les responsabilités.** Chaque fichier fait *une seule chose* :

| Question | Fichier qui y répond |
|---|---|
| Comment transformer du texte en audio ? | `edge_engine.py`, `piper_engine.py` |
| Lequel des deux moteurs utiliser ? | `fallback.py` |
| Comment jouer un fichier audio ? | `player.py` |
| Dans quel ordre lire les morceaux, et quand faire pause ? | `speaker.py` |
| Comment l'utilisateur donne ses ordres ? | `main.py` (terminal) ou `gui.py` (fenêtre) |

Grâce à cette séparation, `main.py` et `gui.py` réutilisent **exactement le même cœur** (`tts/`).
Si demain tu veux une application web, tu n'auras qu'à écrire une nouvelle « façade » :
le reste ne bouge pas.

---

## 2. Le chemin d'un texte, du clavier au haut-parleur

Quand tu cliques sur **▶ Lire** dans la fenêtre :

```
gui.py                speaker.py                fallback.py           edge_engine.py
──────                ──────────                ───────────           ──────────────
on_play()
  └─ démarre un thread ─► speak(texte)
                          │ chunk_text() découpe en morceaux
                          │
                          ├─ synthétise morceau 1 ──► synthesize() ──► Internet OK ?
                          │                              │               oui → mp3
                          │                              └─ non → Piper → wav
                          ├─ prépare morceau 2 (en avance, dans un autre thread)
                          ├─ player.start(morceau 1)  ──► pygame joue le son 🔊
                          ├─ attend la fin…
                          ├─ prépare morceau 3
                          ├─ player.start(morceau 2)
                          └─ …
  ◄── messages "progress" / "done" via une file (queue) ──┘
_poll() met à jour le statut affiché
```

Garde ce schéma en tête pendant ta lecture des sections suivantes.

---

## 3. `config.py` : les réglages

Un simple fichier de **constantes** : voix par défaut, dossiers, raccourci clavier, taille des morceaux…

```python
DEFAULT_VOICE: str = "fr-CA-AntoineNeural"
OUTPUT_DIR: Path = Path(__file__).parent / "output"
```

- `Path(__file__).parent` = le dossier où se trouve `config.py`. Ainsi, `output/` est toujours
  au bon endroit, **peu importe d'où tu lances le programme**.
- Le `/` entre deux `Path` construit un chemin (`pathlib` gère les `\` de Windows pour toi).
- Les noms en MAJUSCULES sont une **convention** Python pour dire « constante, ne pas modifier ».

**Pourquoi un fichier à part ?** Pour changer un réglage (ex. le raccourci `HOTKEY`), tu n'as pas à
fouiller dans le code : tout est au même endroit.

---

## 4. `tts/base.py` : le contrat commun des moteurs

```python
class TTSEngine(ABC):
    extension: str = ".mp3"

    @abstractmethod
    def synthesize(self, text, voice, rate, pitch, volume, output) -> Path: ...

    @abstractmethod
    def list_voices(self) -> list[str]: ...
```

### Classe abstraite (`ABC`)

Une classe abstraite est un **contrat** : elle dit « tout moteur DOIT avoir ces méthodes », sans
les écrire elle-même. `@abstractmethod` empêche de créer un moteur qui aurait oublié une méthode :
Python lève une erreur dès la création de l'objet.

**À quoi ça sert ?** Le reste du code (`Speaker`, `main.py`, `gui.py`) travaille avec un
`TTSEngine` *quelconque*. Il ne sait pas (et n'a pas besoin de savoir) si c'est edge-tts ou Piper.
C'est le **polymorphisme** : même interface, comportements différents.

### Les exceptions personnalisées

```python
class TTSError(Exception): ...                 # toute erreur « normale » (texte vide, mauvaise voix)
class TTSConnectionError(TTSError): ...        # cas particulier : pas d'Internet
```

`TTSConnectionError` **hérite** de `TTSError`. Conséquence :

- `except TTSError` attrape **les deux** (pratique dans `main.py` : on affiche juste le message) ;
- `except TTSConnectionError` attrape **seulement** les coupures réseau (utilisé par
  `fallback.py` pour décider de basculer vers Piper).

Une voix mal écrite ne doit **pas** déclencher la bascule : c'est pour ça qu'on a deux classes.

---

## 5. `tts/edge_engine.py` : la voix en ligne

edge-tts envoie le texte aux serveurs de Microsoft et reçoit un mp3 en retour.

### Valider avant d'appeler le réseau

```python
_PERCENT_RE = re.compile(r"^[+-]\d+%$")
if not _PERCENT_RE.match(rate):
    raise TTSError(f"Vitesse invalide « {rate} » (exemple : +10% ou -20%).")
```

L'expression régulière `^[+-]\d+%$` se lit : *début*, un `+` ou `-`, un ou plusieurs chiffres,
un `%`, *fin*. On vérifie le format **avant** d'appeler Internet : le message d'erreur est plus clair
et on ne perd pas de temps.

### Le monde asynchrone (`async`) caché derrière `asyncio.run()`

edge-tts est une bibliothèque **asynchrone** : ses fonctions sont des `async def` qui doivent être
« attendues » avec `await`. Le reste de notre code est normal (synchrone). Le pont entre les deux :

```python
asyncio.run(communicate.save(str(output)))
```

`asyncio.run()` crée une boucle d'événements, exécute la coroutine jusqu'au bout, puis rend la main.
Résultat : pour le reste du programme, `synthesize()` est une fonction ordinaire. C'est ce qu'on
appelle **encapsuler** une complexité.

### Traduire les erreurs

```python
except ValueError:          → TTSError("Voix invalide…")
except NoAudioReceived:     → TTSError("la voix n'existe probablement pas")
except (aiohttp.ClientError, OSError): → TTSConnectionError("Vérifiez votre connexion")
```

Les erreurs techniques de la bibliothèque sont transformées en **nos** erreurs, avec des messages
en français. `from None` masque l'erreur d'origine dans l'affichage (sinon Python montrerait deux
longues traces d'erreur).

---

## 6. `tts/piper_engine.py` : la voix hors ligne

Piper fait tourner un **réseau de neurones directement sur ton PC** (fichiers `.onnx` dans
`voices/`). Pas besoin d'Internet, mais il produit du `.wav` (d'où `extension = ".wav"`).

### Traduire les réglages d'edge-tts vers Piper

Piper ne comprend pas « +20% ». Il a un `length_scale` (durée relative) :

```python
length_scale = 1 / (1 + rate_pct / 100)
# +100% → 1/2   = 0.5  → deux fois plus court = deux fois plus rapide
#   0%  → 1/1   = 1.0  → normal
# -50%  → 1/0.5 = 2.0  → deux fois plus long  = deux fois plus lent
```

Le `max(0.1, …)` évite une division par zéro si quelqu'un demande `-100%`.
Piper ne sait pas changer le **ton** : le paramètre `pitch` est simplement ignoré.

### Choisir une voix Piper à partir d'une voix edge-tts

```python
def resolve_voice(self, voice):
    lang = voice.split("-")[0].split("_")[0].lower()   # "fr-CA-AntoineNeural" → "fr"
    return PIPER_VOICE_BY_LANG.get(lang, PIPER_DEFAULT_VOICE)
```

Quand Internet coupe, on demandait peut-être `fr-CA-AntoineNeural` : Piper n'a pas cette voix,
alors on garde seulement la **langue** et on prend la voix Piper française.

### Le cache des modèles

```python
self._loaded: dict[str, PiperVoice] = {}
if name not in self._loaded:
    self._loaded[name] = PiperVoice.load(model)
```

Charger un modèle de 60 Mo prend environ une seconde. On le garde en mémoire après le premier
chargement : les phrases suivantes sont instantanées. C'est un **cache**.

### Import « paresseux »

```python
def _load(self, name):
    from piper import PiperVoice   # import DANS la fonction
```

Piper importe `onnxruntime`, qui est lourd. En l'important seulement quand on en a besoin,
l'application démarre plus vite quand Internet fonctionne (cas le plus courant).

---

## 7. `tts/fallback.py` : la bascule automatique

`FallbackEngine` est **lui-même un `TTSEngine`** qui contient deux autres moteurs :

```python
class FallbackEngine(TTSEngine):
    def __init__(self, primary, backup, notify=print, retry_after=60): ...
```

C'est le patron de conception (*design pattern*) **Décorateur / Composite** : on enveloppe des
objets pour ajouter un comportement, sans que le code qui les utilise s'en rende compte.
`Speaker` appelle `engine.synthesize(...)` sans savoir qu'il y a deux moteurs derrière.

### La logique

```python
if not self.offline:
    try:
        return self.primary.synthesize(...)           # 1. on essaie edge-tts
    except TTSConnectionError:                        # 2. pas d'Internet ?
        self._offline_since = time.monotonic()        #    on note l'heure de la coupure
        self.notify("Pas de connexion Internet : …")  #    on prévient l'utilisateur
return self.backup.synthesize(...)                    # 3. on utilise Piper
```

### Pourquoi retenir l'heure de la coupure ?

Sans ça, chaque phrase réessaierait Internet, attendrait l'échec, puis basculerait : lent et
agaçant. Avec `_offline_since`, on reste sur Piper pendant 60 s, puis la propriété `offline`
remet le compteur à zéro et on retente edge-tts.

`time.monotonic()` est une horloge qui **ne recule jamais** (contrairement à l'heure du système,
qui peut changer). C'est la bonne horloge pour mesurer des durées.

### `notify` : une fonction passée en paramètre

Par défaut `notify=print` (le message s'affiche dans le terminal). La GUI passe sa propre fonction
qui envoie le message dans sa file d'événements. Le moteur ne sait rien de l'affichage :
il appelle juste « la fonction qu'on lui a donnée ». On appelle ça un **callback**.

### `@property`

```python
@property
def offline(self) -> bool: ...
```

Permet d'écrire `engine.offline` (sans parenthèses) alors que c'est en réalité un calcul.

---

## 8. `tts/player.py` : jouer le son

Petites fonctions autour de `pygame.mixer.music` :

| Fonction | Rôle |
|---|---|
| `start(path)` | lance la lecture et rend la main **immédiatement** |
| `is_playing()` | le son est-il en train de jouer ? |
| `pause()` / `unpause()` | fige / reprend au même endroit |
| `stop()` | arrête **et libère le fichier** (`unload`) |
| `play(path)` | version « bloquante » : `start` + attendre la fin (utilisée par `--save`) |

**Pourquoi `unload()` ?** Sous Windows, un fichier ouvert est verrouillé : impossible de le
réécrire. Comme on réutilise `chunk_0.mp3` et `chunk_1.mp3`, il faut le libérer avant.

**`os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")`** doit être exécuté *avant*
`import pygame`, sinon pygame affiche un message publicitaire. C'est pour ça que l'import est
après (et le commentaire `# noqa: E402` dit aux outils de vérification que c'est voulu).

> **pygame-ce** : la version communautaire de pygame. On l'installe sous ce nom mais on l'importe
> avec `import pygame`. On l'a choisie car `pygame` n'avait pas de version pour Python 3.14.

---

## 9. `tts/text_utils.py` : découper le texte

### Pourquoi découper ?

Synthétiser un texte de 3 pages prend du temps. Si on attend tout avant de jouer, l'utilisateur
patiente. En découpant, on joue la **première phrase dès qu'elle est prête** (≈ 0,7 s).

### Comment

```python
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
```

- `(?<=[.!?…])\s+` : des espaces **précédés** d'une ponctuation de fin. Le `(?<=…)` est un
  *lookbehind* : il vérifie ce qui précède sans le « manger », donc le point reste dans la phrase.
- `|\n+` : ou un ou plusieurs sauts de ligne.

`chunk_text()` fait ensuite trois choses :

1. découpe en phrases ;
2. coupe aux espaces les phrases **trop longues** (`_split_long`) ;
3. **regroupe** les phrases courtes jusqu'à `CHUNK_MAX_CHARS` (150), **sauf la première**
   qui reste seule pour démarrer le plus vite possible.

Pourquoi regrouper ? Chaque morceau = un appel réseau. Lire « Oui. Non. D'accord. » en trois
appels serait lent et créerait des petits silences.

---

## 10. `tts/speaker.py` : le chef d'orchestre

C'est le fichier le plus subtil. Prends ton temps.

### 10.1 Le préchargement (*prefetch*)

```python
with ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(synth, 0)          # commence à préparer le morceau 0
    while i < len(chunks):
        path, version = future.result()     # attend que le morceau i soit prêt
        future = pool.submit(synth, i + 1)  # lance DÉJÀ la préparation du suivant
        self._play(path, version)           # joue le morceau i pendant ce temps
        i += 1
```

- `ThreadPoolExecutor` : un « employé » (thread) qui exécute des tâches en arrière-plan.
- `pool.submit(f, x)` : « fais `f(x)` quand tu peux » → renvoie un **`Future`**, une promesse
  de résultat.
- `future.result()` : « donne-moi le résultat » (attend s'il n'est pas encore prêt ; relance
  l'exception si la tâche a échoué).

Pendant que le morceau *i* joue, le morceau *i+1* se prépare. Quand *i* finit, *i+1* est
déjà prêt : **pas de blanc** entre les phrases.

### 10.2 Les deux fichiers en alternance

```python
path = OUTPUT_DIR / f"chunk_{index % 2}{self.engine.extension}"
```

`index % 2` vaut 0, 1, 0, 1… Le morceau qui joue et celui qui se prépare n'utilisent jamais le
même fichier. On n'a besoin que de deux fichiers, quelle que soit la longueur du texte.

### 10.3 Les `threading.Event` : des drapeaux partagés entre threads

```python
self._stop_event = threading.Event()   # levé = « arrête-toi »
self._running = threading.Event()      # levé = « pas en pause »
```

Un `Event` est un drapeau thread-safe : `set()` le lève, `clear()` le baisse, `wait()` attend
qu'il soit levé. Le bouton Stop (thread de l'interface) lève `_stop_event` ; le thread de lecture
le voit et s'arrête proprement.

`_running` est « à l'envers » (levé = on joue) parce que `wait()` attend qu'un drapeau soit
**levé** : pendant la pause, le thread de lecture fait `self._running.wait(0.05)` et dort jusqu'à
la reprise.

### 10.4 Pause et changement de réglages : le numéro de version

Problème : on met en pause, on change la voix, on reprend. Le morceau en cours a été fabriqué
avec l'**ancienne** voix → il faut le refaire.

Solution : un **compteur de version**.

```python
def resume(self, **settings):
    with self._lock:
        changed = any(self._settings.get(k) != v for k, v in settings.items())
        if changed:
            self._settings.update(settings)
            self._version += 1          # « les réglages ont changé »
```

- Chaque morceau retient la version avec laquelle il a été synthétisé.
- Pendant la lecture, `_play()` compare : si `self._version != version`, le morceau est
  **périmé** → `_play` renvoie `False` → on resynthétise le **même** morceau.

**Pourquoi un numéro plutôt que comparer les réglages ?** Au début, on comparait les réglages
pendant la pause. Le test automatique a trouvé un bug : en cliquant Pause → Reprendre en moins de
50 ms, le thread de lecture ne « voyait » jamais la pause et ratait le changement. Avec un numéro
qui ne fait qu'augmenter, impossible de manquer un changement, même très rapide.

### 10.5 Le verrou (`threading.Lock`)

```python
with self._lock:
    settings, version = dict(self._settings), self._version
```

Deux threads lisent/écrivent `_settings` et `_version`. Sans verrou, l'un pourrait lire *la
nouvelle voix* avec *l'ancienne version*. `with self._lock:` garantit qu'un seul thread à la fois
exécute ce bloc.

### 10.6 Une course subtile (*race condition*)

```python
def pause(self):
    self._running.clear()   # 1. on marque la pause
    player.pause()          # 2. on fige l'audio
```

Et dans `_play()` :

```python
if not player.is_playing():
    if self.paused:   # l'audio est arrêté… mais est-ce parce qu'on est en pause ?
        continue
    return True       # non : le morceau est vraiment fini
```

Quand l'audio est en pause, pygame répond `is_playing() == False`, comme si c'était fini !
Grâce à l'**ordre** dans `pause()` (marquer d'abord, figer ensuite), si l'audio paraît arrêté
à cause de la pause, `self.paused` est forcément déjà vrai. Ce genre de détail est typique de la
programmation multi-thread.

---

## 11. `tts/hotkey.py` : le raccourci global

```python
listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+l": callback})
listener.daemon = True
listener.start()
```

- **pynput** écoute le clavier de **tout le système**, même quand la fenêtre n'a pas le focus.
- L'écoute tourne dans son propre thread. `daemon = True` : ce thread s'arrête tout seul quand
  le programme se termine (sinon il empêcherait de quitter).
- **pyperclip** lit le presse-papiers sur Windows, macOS et Linux.

⚠️ Le `callback` s'exécute dans le thread de pynput : il doit être **rapide**. C'est pourquoi
`main.py` lance la lecture dans un *nouveau* thread, et `gui.py` dépose juste un message dans
sa file.

> Anecdote de test : pynput ignore volontairement les touches *simulées* par un programme
> (`if not injected`). Pour tester le raccourci, on a donc envoyé les événements directement à
> son gestionnaire.

---

## 12. `main.py` : la ligne de commande

### `argparse`

```python
parser.add_argument("text", nargs="?")            # argument positionnel optionnel
parser.add_argument("--rate", default="+0%")      # option avec valeur
parser.add_argument("--offline", action="store_true")  # interrupteur (vrai si présent)
```

`argparse` génère automatiquement l'aide : essaie `uv run main.py --help`.

> **Piège** : `--rate -10%` ne marche pas, argparse croit que `-10%` est une option.
> Écris `--rate=-10%`.

### Le choix du mode

```python
if args.list_voices:   …
if args.hotkey:        hotkey_mode(...)
elif args.file:        lire le fichier
elif args.text is not None:  lire le texte
else:                  interactive(...)
```

On teste `args.text is not None` (et pas `if args.text`) pour qu'un texte vide `""` donne une
**erreur claire** au lieu d'ouvrir le mode interactif.

### Les codes de sortie

`main()` renvoie `0` (succès), `1` (erreur) ou `130` (interrompu par Ctrl+C, une convention
Unix). `sys.exit(main())` les transmet au système : utile pour les scripts.

### `sys.stdout.reconfigure(encoding="utf-8")`

La console Windows n'est pas toujours en UTF-8 : sans cette ligne, un `é` pourrait faire planter
`print`.

### `nonlocal` dans `hotkey_mode`

```python
current: threading.Thread | None = None
def on_hotkey():
    nonlocal current
    current = threading.Thread(...)
```

Une fonction interne ne peut pas *réassigner* une variable de la fonction englobante sans
`nonlocal`. On s'en sert pour savoir si une lecture est déjà en cours (2ᵉ appui = Stop).

---

## 13. `gui.py` : l'interface graphique

### La règle d'or de tkinter

> **Seul le thread principal a le droit de toucher aux widgets.**

Or la synthèse doit tourner dans un autre thread (sinon la fenêtre se fige pendant l'appel
réseau). Comment le thread de travail informe-t-il l'interface ? Par une **file de messages** :

```python
self.events: queue.Queue[tuple[str, str]] = queue.Queue()

# Dans le thread de travail :
self.events.put(("progress", "2/5"))

# Dans le thread principal, toutes les 100 ms :
def _poll(self):
    while True:
        kind, payload = self.events.get_nowait()   # lève queue.Empty s'il n'y a rien
        if kind == "progress": self._set_status(...)
        ...
    self.after(100, self._poll)                    # se reprogramme
```

- `queue.Queue` est **thread-safe** : plusieurs threads peuvent y écrire sans risque.
- `self.after(100, f)` demande à tkinter d'appeler `f` dans 100 ms, **dans le thread principal**.
  `_poll` se reprogramme lui-même : c'est une boucle qui ne bloque jamais la fenêtre.

Types de messages : `hotkey`, `progress`, `info`, `error`, `done`.

### Les réglages sont lus dans le thread principal

```python
def _settings(self) -> dict[str, str]:
    return {"voice": self.voice_menu.get().strip(),
            "rate": f"{int(self.rate.get()):+d}%", ...}
```

On lit les curseurs **avant** de lancer le thread, et on lui passe un simple dictionnaire.
`f"{20:+d}"` donne `"+20"` (le `+` force l'affichage du signe), exactement le format d'edge-tts.

### `self.busy`

Empêche de lancer deux lectures en même temps : les boutons Lire/Enregistrer sont désactivés
pendant le travail. Le bouton Pause n'est actif **que pendant une lecture**.

### `**settings` : déballer un dictionnaire

```python
self.speaker.speak(text, **settings)
# équivaut à : speak(text, voice="...", rate="...", pitch="...", volume="...")
```

### Le `lambda` dans `_add_slider`

```python
command=lambda v: value_label.configure(text=f"{int(v):+d}{unit}")
```

Une petite fonction anonyme. Elle « capture » `value_label` et `unit` de *cet* appel de
`_add_slider` : chaque curseur met à jour **sa propre** étiquette.

### `destroy()` surchargée

À la fermeture de la fenêtre, on arrête la lecture et l'écoute du clavier avant d'appeler le
`destroy()` d'origine (`super().destroy()`). Sinon le son pourrait continuer après la fermeture.

---

## 14. Les tests

Lancer : `uv run pytest` (ou `uv run pytest -m "not network"` sans Internet).

| Fichier | Ce qu'il vérifie |
|---|---|
| `test_engines.py` | edge-tts : validation, création de mp3, liste des voix, voix inconnue |
| `test_phase3.py` | découpage du texte, bascule vers Piper, Piper lui-même |
| `test_speaker.py` | pause / reprise / changement de réglages / stop |

### Techniques utilisées

- **`@pytest.fixture`** : prépare un objet réutilisable (`engine`, `fake_player`).
- **`@pytest.mark.parametrize`** : lance le même test avec plusieurs valeurs.
- **`pytest.raises(TTSError, match="vide")`** : vérifie qu'une erreur est bien levée, avec le bon
  message.
- **`tmp_path`** : un dossier temporaire fourni par pytest, effacé après.
- **Faux objets (*fakes*)** : `FakeEngine` simule une coupure réseau sans débrancher le câble ;
  `RecordingEngine` note les appels au lieu de produire du son ; `FakePlayer` simule un son de
  0,4 s. Les tests sont ainsi **rapides, silencieux et reproductibles**.
- **`monkeypatch.setattr`** : remplace temporairement les fonctions de `player` par celles du
  faux lecteur, le temps d'un test.
- **`@pytest.mark.network`** / **`skipif`** : marque les tests qui ont besoin d'Internet ou des
  modèles Piper.

Le test `test_changed_settings_redo_current_sentence` a trouvé un **vrai bug** (section 10.4) :
c'est exactement à ça que servent les tests.

---

## 15. uv et `pyproject.toml`

**uv** remplace `pip` + `venv` (et il est beaucoup plus rapide).

| Commande | Rôle |
|---|---|
| `uv sync` | crée `.venv` et installe exactement les versions de `uv.lock` |
| `uv add paquet` | ajoute une dépendance (met à jour `pyproject.toml` et `uv.lock`) |
| `uv run fichier.py` | exécute avec le bon environnement, sans rien activer |

- **`pyproject.toml`** : ce que tu *veux* (« edge-tts version 7 ou plus »).
- **`uv.lock`** : ce qui est *réellement installé* (versions exactes de tout, y compris les
  dépendances des dépendances). Sur un autre PC, `uv sync` recrée le même environnement.
- `[dependency-groups] dev` : `pytest` sert à développer, pas à faire tourner l'application.
- `package = false` : c'est une application, pas une bibliothèque à publier.
- `pythonpath = ["."]` (section pytest) : permet aux tests de faire `from tts import …`.

---

## 16. Les concepts Python à retenir

| Concept | Où le voir |
|---|---|
| Classe abstraite, héritage, polymorphisme | `base.py`, les deux moteurs |
| Exceptions personnalisées, hiérarchie | `base.py`, `fallback.py` |
| Composition (un objet qui contient d'autres objets) | `FallbackEngine`, `Speaker` |
| Callbacks (passer une fonction en paramètre) | `notify`, `on_progress`, `hotkey` |
| `async` / `asyncio.run` | `edge_engine.py` |
| Threads, `Event`, `Lock`, `Queue`, `ThreadPoolExecutor`, `Future` | `speaker.py`, `gui.py` |
| Race condition et ses solutions | `speaker.py` (sections 10.4 et 10.6) |
| Expressions régulières | `edge_engine.py`, `text_utils.py` |
| `pathlib.Path` | partout |
| `@property` | `fallback.py`, `speaker.py` |
| Type hints (`str | None`, `list[str]`, `Callable[[int, int], None]`) | partout |
| f-strings avec format (`f"{x:+d}"`) | `gui.py` |
| `*args`, `**kwargs` | `gui.py`, `speaker.py` |
| Cache, import paresseux | `piper_engine.py` |

---

## 17. Exercices pour progresser

Du plus facile au plus difficile. Après chaque modification : `uv run pytest`.

1. **Changer le raccourci** pour `<ctrl>+<shift>+s` dans `config.py`.
2. **Ajouter une voix** à `RECOMMENDED_VOICES` (trouve-la avec `uv run main.py --list-voices`).
3. **Bouton « Coller »** dans la GUI qui remplace le texte par le presse-papiers
   (indice : `read_clipboard()` existe déjà).
4. **Écrire un test** pour `split_sentences` avec des points de suspension `…`.
5. **Charger toutes les voix** dans le menu déroulant au démarrage, dans un thread
   (indice : même principe que `_read_worker` + un nouveau type de message dans `_poll`).
6. **Appliquer les réglages sans pause** : si on bouge un curseur pendant la lecture, la
   *prochaine* phrase utilise la nouvelle valeur (indice : appeler une méthode du `Speaker` qui
   met à jour `_settings` et incrémente `_version`… mais sans redémarrer la phrase en cours).
7. **Surligner la phrase en cours de lecture** dans la zone de texte
   (indice : `on_progress` connaît le numéro du morceau ; `textbox.tag_add`).
