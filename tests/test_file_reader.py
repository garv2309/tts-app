"""Tests de l'extraction du texte des fichiers (txt, pdf, docx)."""

from pathlib import Path

import pytest

from tts import TTSError
from tts.file_reader import clean_pdf_text, read_document


def make_pdf(path: Path, lines: list[str]) -> None:
    """Écrit un PDF minimal d'une page, une ligne de texte par élément de lines."""
    commands = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]
    commands += [f"({line}) Tj T*" for line in lines]
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    # La table xref donne la position (en octets) de chaque objet dans le fichier
    data = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(data)
    data += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    data += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    data += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    path.write_bytes(data)


# --- Nettoyage du texte PDF ---


def test_clean_pdf_joins_wrapped_lines() -> None:
    assert clean_pdf_text("Une phrase coupée\nen deux lignes.") == "Une phrase coupée en deux lignes."


def test_clean_pdf_rejoins_hyphenated_words() -> None:
    assert clean_pdf_text("un bel exem-\nple") == "un bel exemple"


def test_clean_pdf_keeps_paragraphs() -> None:
    assert clean_pdf_text("Fin.  \n\n\n\nDébut suivant.") == "Fin.\n\nDébut suivant."


# --- Lecture des fichiers ---


def test_read_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    make_pdf(pdf, ["Bonjour, ceci est l'été à", "Québec : un exem-", "ple de PDF."])
    assert read_document(pdf) == "Bonjour, ceci est l'été à Québec : un exemple de PDF."


def test_read_docx(tmp_path: Path) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph("Premier paragraphe.")
    document.add_paragraph("")
    document.add_paragraph("Deuxième paragraphe.")
    path = tmp_path / "doc.docx"
    document.save(str(path))
    assert read_document(path) == "Premier paragraphe.\nDeuxième paragraphe."


def test_read_txt_utf8_and_cp1252(tmp_path: Path) -> None:
    utf8 = tmp_path / "utf8.txt"
    utf8.write_text("Été à Québec", encoding="utf-8")
    windows = tmp_path / "windows.txt"
    windows.write_text("Été à Québec", encoding="cp1252")
    assert read_document(utf8) == read_document(windows) == "Été à Québec"


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("image.png", b"\x89PNG", "non pris en charge"),
        ("vide.txt", b"  \n ", "ne contient pas de texte"),
        ("faux.pdf", b"pas un pdf", "illisible"),
        ("faux.docx", b"pas un docx", "illisible"),
    ],
)
def test_bad_files_give_clear_errors(tmp_path: Path, name: str, content: bytes, message: str) -> None:
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(TTSError, match=message):
        read_document(path)


def test_scanned_pdf_without_text(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    make_pdf(pdf, [])
    with pytest.raises(TTSError, match="scanné"):
        read_document(pdf)


def test_missing_file() -> None:
    with pytest.raises(TTSError, match="introuvable"):
        read_document(Path("nexiste_pas.pdf"))
