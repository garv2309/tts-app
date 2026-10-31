"""Extraction du texte des fichiers (txt, md, pdf, docx) pour les lire à voix haute."""

import re
import zipfile
from pathlib import Path

from tts.base import TTSError

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".txt", ".md", ".pdf", ".docx")

# Mot coupé par un tiret en fin de ligne : « exem-\nple » → « exemple »
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
# Retour à la ligne isolé (pas une ligne vide) : simple fin de ligne visuelle, pas un paragraphe
_SINGLE_NEWLINE = re.compile(r"(?<!\n)\n(?!\n)")


def read_document(path: Path) -> str:
    """Renvoie le texte du fichier, prêt à être lu."""
    if not path.is_file():
        raise TTSError(f"Fichier « {path} » introuvable.")
    extension = path.suffix.lower()
    if extension == ".pdf":
        text = clean_pdf_text(_read_pdf(path))
    elif extension == ".docx":
        text = _read_docx(path)
    elif extension in (".txt", ".md"):
        text = _read_plain(path)
    else:
        formats = ", ".join(SUPPORTED_EXTENSIONS)
        raise TTSError(f"Format « {extension or path.name} » non pris en charge (formats : {formats}).")

    if not text.strip():
        raise TTSError(f"Le fichier « {path.name} » ne contient pas de texte à lire.")
    return text


def clean_pdf_text(text: str) -> str:
    """Recolle les lignes d'un PDF pour que les phrases ne soient pas coupées en morceaux."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)  # espaces en fin de ligne
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _SINGLE_NEWLINE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)  # on garde au plus une ligne vide entre paragraphes
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _read_plain(path: Path) -> str:
    # Les fichiers créés avec le Bloc-notes Windows sont parfois en cp1252 plutôt qu'en UTF-8
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1252", errors="replace")
    except OSError as exc:
        raise TTSError(f"Impossible de lire « {path.name} » ({exc}).") from None


def _read_pdf(path: Path) -> str:
    # Import ici : inutile de charger pypdf si on ne lit jamais de PDF
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise TTSError(f"« {path.name} » est protégé par un mot de passe.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, ValueError) as exc:
        raise TTSError(f"PDF « {path.name} » illisible ou endommagé ({exc}).") from None

    if not any(page.strip() for page in pages):
        # Un PDF scanné ne contient que des images : il faudrait de l'OCR pour en tirer du texte
        raise TTSError(
            f"« {path.name} » ne contient pas de texte sélectionnable (probablement un document scanné)."
        )
    # Ligne vide entre les pages : la fin d'une page compte comme une fin de paragraphe
    return "\n\n".join(pages)


def _read_docx(path: Path) -> str:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = Document(str(path))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, OSError):
        raise TTSError(f"Document Word « {path.name} » illisible ou endommagé.") from None
    # Un paragraphe Word = une ligne : le découpage en phrases s'en sert comme coupure
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())
