import hashlib
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".docx"}


@dataclass
class LoadedPage:
    text: str
    page: int | None


@dataclass
class LoadedDocument:
    document_id: str
    source: str
    title: str
    pages: list[LoadedPage]


def compute_document_id(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def _load_txt_or_md(path: Path, content: bytes) -> list[LoadedPage]:
    text = content.decode("utf-8", errors="replace")
    return [LoadedPage(text=text, page=None)]


def _load_pdf(path: Path) -> list[LoadedPage]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(LoadedPage(text=text, page=i))
    return pages


def _load_docx(path: Path) -> list[LoadedPage]:
    doc = DocxDocument(str(path))
    text = "\n".join(p.text for p in doc.paragraphs)
    return [LoadedPage(text=text, page=None)]


def load_document(path: str | Path) -> LoadedDocument:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document type: {suffix}")

    content = path.read_bytes()
    document_id = compute_document_id(content)

    if suffix in (".txt", ".md", ".markdown"):
        pages = _load_txt_or_md(path, content)
    elif suffix == ".pdf":
        pages = _load_pdf(path)
    elif suffix == ".docx":
        pages = _load_docx(path)
    else:
        raise ValueError(f"Unsupported document type: {suffix}")

    return LoadedDocument(
        document_id=document_id,
        source=path.name,
        title=path.stem,
        pages=pages,
    )
