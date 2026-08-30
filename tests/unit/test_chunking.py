from app.ingestion.chunking import chunk_document, compute_chunk_id, normalize_text
from app.ingestion.loaders import LoadedDocument, LoadedPage


def _doc(text: str, page: int | None = None) -> LoadedDocument:
    return LoadedDocument(
        document_id="doc123",
        source="test.txt",
        title="test",
        pages=[LoadedPage(text=text, page=page)],
    )


def test_normalize_text_collapses_whitespace_and_blank_lines():
    raw = "Hello   world\r\n\r\n\r\nSecond   line\r"
    normalized = normalize_text(raw)
    assert "\r" not in normalized
    assert "\n\n\n" not in normalized
    assert "Hello world" in normalized


def test_chunking_preserves_metadata():
    text = "word " * 2000
    doc = _doc(text, page=3)
    chunks = chunk_document(doc, chunk_size_tokens=50, overlap_tokens=10)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata.document_id == "doc123"
        assert chunk.metadata.source == "test.txt"
        assert chunk.metadata.page == 3
        assert chunk.metadata.chunk_id
        assert chunk.metadata.hash


def test_chunking_respects_approximate_size_limit():
    text = "word " * 2000
    doc = _doc(text)
    chunk_size_tokens = 50
    chunks = chunk_document(doc, chunk_size_tokens=chunk_size_tokens, overlap_tokens=0)

    max_chars = chunk_size_tokens * 4 * 1.5  # generous slack for overlap/boundary effects
    assert all(len(c.text) <= max_chars for c in chunks)


def test_chunking_deduplicates_identical_chunks():
    text = "repeat me. " * 5
    doc = _doc(text)
    chunks = chunk_document(doc, chunk_size_tokens=3, overlap_tokens=0)

    hashes = [c.metadata.hash for c in chunks]
    assert len(hashes) == len(set(hashes))


def test_chunk_id_is_deterministic():
    id1 = compute_chunk_id("doc1", 1, 0, "hello")
    id2 = compute_chunk_id("doc1", 1, 0, "hello")
    id3 = compute_chunk_id("doc1", 1, 1, "hello")
    assert id1 == id2
    assert id1 != id3


def test_chunking_skips_empty_pages():
    doc = LoadedDocument(
        document_id="doc1",
        source="s.txt",
        title="s",
        pages=[LoadedPage(text="   ", page=1), LoadedPage(text="real content here", page=2)],
    )
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].metadata.page == 2
