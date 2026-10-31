"""Interface graphique simple (customtkinter)."""

import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from config import DEFAULT_VOICE, HOTKEY, RECOMMENDED_VOICES
from tts import TTSError, create_engine
from tts.file_reader import SUPPORTED_EXTENSIONS, read_document
from tts.hotkey import read_clipboard, start_listener
from tts.speaker import Speaker


class TTSApp(ctk.CTk):
    """Fenêtre principale : texte, réglages de voix et boutons Lire / Stop / Enregistrer."""

    def __init__(self, enable_hotkey: bool = True) -> None:
        super().__init__()
        self.title("Lecteur vocal")
        self.geometry("620x500")
        self.minsize(480, 400)

        # Les threads (synthèse, raccourci) déposent leurs messages ici ;
        # seule la boucle Tk touche aux widgets, dans _poll()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.engine = create_engine(notify=lambda msg: self.events.put(("info", msg)))
        self.speaker = Speaker(self.engine)
        self.busy = False
        self.progress = ""

        self._build_widgets()
        self.listener = None
        if enable_hotkey:
            self.listener = start_listener(HOTKEY, lambda: self.events.put(("hotkey", "")))
        self.after(100, self._poll)

    # --- Construction de l'interface ---

    def _build_widgets(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(self, wrap="word", font=("Segoe UI", 14))
        self.textbox.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")
        self.textbox.insert("1.0", "Bonjour, je suis votre assistant vocal.")

        settings = ctk.CTkFrame(self)
        settings.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        settings.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(settings, text="Voix").grid(row=0, column=0, padx=10, pady=6, sticky="w")
        self.voice_menu = ctk.CTkComboBox(settings, values=RECOMMENDED_VOICES)
        self.voice_menu.set(DEFAULT_VOICE)
        self.voice_menu.grid(row=0, column=1, columnspan=2, padx=10, pady=6, sticky="ew")

        # Chaque curseur : (étiquette, min, max, unité affichée/envoyée à edge-tts)
        self.rate = self._add_slider(settings, 1, "Vitesse", -50, 50, "%")
        self.pitch = self._add_slider(settings, 2, "Ton", -20, 20, "Hz")
        self.volume = self._add_slider(settings, 3, "Volume", -50, 50, "%")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=16, pady=8, sticky="ew")
        buttons.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.open_button = ctk.CTkButton(buttons, text="📂 Ouvrir", command=self.on_open)
        self.open_button.grid(row=0, column=4, padx=4, sticky="ew")
        self.play_button = ctk.CTkButton(buttons, text="▶ Lire", command=self.on_play)
        self.play_button.grid(row=0, column=0, padx=4, sticky="ew")
        self.pause_button = ctk.CTkButton(
            buttons, text="⏸ Pause", command=self.on_pause, state="disabled"
        )
        self.pause_button.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(buttons, text="■ Stop", command=self.on_stop).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        self.save_button = ctk.CTkButton(buttons, text="💾 Enregistrer", command=self.on_save)
        self.save_button.grid(row=0, column=3, padx=4, sticky="ew")

        self.status = ctk.CTkLabel(self, text="Prêt", anchor="w")
        self.status.grid(row=3, column=0, padx=20, pady=(0, 4), sticky="ew")
        ctk.CTkLabel(
            self,
            text=f"Astuce : copiez du texte n'importe où puis appuyez sur {HOTKEY}",
            anchor="w",
            text_color="gray50",
        ).grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")

    def _add_slider(
        self, parent: ctk.CTkFrame, row: int, label: str, low: int, high: int, unit: str
    ) -> ctk.CTkSlider:
        """Ajoute un curseur avec son étiquette et sa valeur affichée."""
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w")
        value_label = ctk.CTkLabel(parent, text=f"+0{unit}", width=60)
        value_label.grid(row=row, column=2, padx=10, pady=6)
        slider = ctk.CTkSlider(
            parent,
            from_=low,
            to=high,
            number_of_steps=high - low,
            command=lambda v: value_label.configure(text=f"{int(v):+d}{unit}"),
        )
        slider.set(0)
        slider.grid(row=row, column=1, padx=10, pady=6, sticky="ew")
        return slider

    # --- Actions des boutons ---

    def on_play(self) -> None:
        if self.busy:
            return
        text = self.textbox.get("1.0", "end").strip()
        self._run_in_thread(self._read_worker, text, self._settings())
        self.pause_button.configure(state="normal")

    def on_pause(self) -> None:
        """Bascule Pause / Reprendre. À la reprise, les réglages actuels sont appliqués."""
        if self.speaker.paused:
            self.speaker.resume(**self._settings())
            self.pause_button.configure(text="⏸ Pause")
            self._set_status(self._progress_text())
        else:
            self.speaker.pause()
            self.pause_button.configure(text="▶ Reprendre")
            self._set_status("En pause : vous pouvez changer la voix ou les réglages.")

    def on_stop(self) -> None:
        self.speaker.stop()

    def on_save(self) -> None:
        if self.busy:
            return
        filename = filedialog.asksaveasfilename(
            title="Enregistrer l'audio",
            defaultextension=".mp3",
            filetypes=[("Fichier MP3", "*.mp3")],
        )
        if filename:
            text = self.textbox.get("1.0", "end").strip()
            self._run_in_thread(self._save_worker, text, self._settings(), Path(filename))

    def on_open(self) -> None:
        """Charge le texte d'un fichier dans la zone de texte (sans lancer la lecture)."""
        if self.busy:
            return
        filename = filedialog.askopenfilename(
            title="Ouvrir un fichier à lire",
            filetypes=[("Documents", SUPPORTED_EXTENSIONS), ("Tous les fichiers", "*")],
        )
        if filename:
            # Un gros PDF peut prendre quelques secondes : thread pour ne pas figer la fenêtre
            self._run_in_thread(self._open_worker, Path(filename), status="Ouverture du fichier…")

    def on_hotkey(self) -> None:
        """Raccourci global : arrête la lecture, ou lit le presse-papiers."""
        if self.busy:
            self.on_stop()
            return
        text = read_clipboard().strip()
        if not text:
            self._set_status("Le presse-papiers ne contient pas de texte.", error=True)
            return
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self.on_play()

    # --- Travail en arrière-plan ---

    def _settings(self) -> dict[str, str]:
        """Lit les réglages ici, dans le thread principal, pour les passer au thread."""
        return {
            "voice": self.voice_menu.get().strip(),
            "rate": f"{int(self.rate.get()):+d}%",
            "pitch": f"{int(self.pitch.get()):+d}Hz",
            "volume": f"{int(self.volume.get()):+d}%",
        }

    def _run_in_thread(self, target, *args, status: str = "Synthèse en cours…") -> None:  # noqa: ANN001
        """Lance target dans un thread pour ne pas figer la fenêtre."""
        self._set_busy(True)
        self._set_status(status)
        threading.Thread(target=target, args=args, daemon=True).start()

    def _read_worker(self, text: str, settings: dict[str, str]) -> None:
        """Exécuté dans le thread : ne touche jamais aux widgets directement."""
        try:
            self.speaker.speak(
                text,
                on_progress=lambda i, n: self.events.put(("progress", f"{i}/{n}")),
                **settings,
            )
            self.events.put(("done", "Prêt"))
        except TTSError as exc:
            self.events.put(("error", str(exc)))

    def _save_worker(self, text: str, settings: dict[str, str], output: Path) -> None:
        try:
            path = self.engine.synthesize(text, output=output, **settings)
            self.events.put(("done", f"Audio enregistré dans {path}"))
        except TTSError as exc:
            self.events.put(("error", str(exc)))

    def _open_worker(self, path: Path) -> None:
        try:
            text = read_document(path)
            self.events.put(("loaded", text))
            self.events.put(("done", f"« {path.name} » chargé ({len(text)} caractères) : cliquez sur ▶ Lire."))
        except TTSError as exc:
            self.events.put(("error", str(exc)))

    def _poll(self) -> None:
        """Traite toutes les 100 ms les messages venus des autres threads."""
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "hotkey":
                self.on_hotkey()
            elif kind == "progress":
                self.progress = payload
                if not self.speaker.paused:
                    self._set_status(self._progress_text())
            elif kind == "loaded":
                self.textbox.delete("1.0", "end")
                self.textbox.insert("1.0", payload)
            elif kind == "info":
                self._set_status(payload)
            elif kind == "error":
                self._set_busy(False)
                self._set_status(f"Erreur : {payload}", error=True)
            elif kind == "done":
                self._set_busy(False)
                self._set_status(payload)
        self.after(100, self._poll)

    # --- Petits utilitaires ---

    def _progress_text(self) -> str:
        offline = " (hors ligne, Piper)" if self.engine.offline else ""
        return f"Lecture… morceau {self.progress}{offline}"

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.play_button.configure(state=state)
        self.save_button.configure(state=state)
        self.open_button.configure(state=state)
        if not busy:
            # La pause n'a de sens que pendant une lecture
            self.pause_button.configure(state="disabled", text="⏸ Pause")

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.configure(text=text, text_color="#e05555" if error else ("gray10", "gray90"))

    def destroy(self) -> None:
        self.speaker.stop()
        if self.listener:
            self.listener.stop()
        super().destroy()


def main() -> None:
    ctk.set_appearance_mode("system")
    app = TTSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
