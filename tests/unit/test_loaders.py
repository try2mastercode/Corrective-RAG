import pytest

from app.ingestion.loaders import compute_document_id, load_document


def test_compute_document_id_is_deterministic_and_content_based():
    id1 = compute_document_id(b"hello")
    id2 = compute_document_id(b"hello")
    id3 = compute_document_id(b"world")
    assert id1 == id2
    assert id1 != id3


def test_load_txt_document(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("Hello from a text file.", encoding="utf-8")

    doc = load_document(path)

    assert doc.source == "note.txt"
    assert doc.title == "note"
    assert len(doc.pages) == 1
    assert "Hello from a text file." in doc.pages[0].text
    assert doc.pages[0].page is None


def test_load_document_rejects_unsupported_extension(tmp_path):
    path = tmp_path / "note.xyz"
    path.write_text("data", encoding="utf-8")

    with pytest.raises(ValueError):
        load_document(path)


def test_load_document_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / "missing.txt")
