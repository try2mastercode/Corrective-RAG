from app.core.models import RetrievedChunk
from app.generation.evidence import build_evidence


def _chunk(chunk_id, text, source="doc.txt", source_type="LOCAL_DOCUMENT", page=None):
    metadata = {"page": page} if page else {}
    return RetrievedChunk(
        chunk_id=chunk_id, text=text, score=0.8, source=source, metadata=metadata, source_type=source_type
    )


def test_build_evidence_assigns_sequential_ids():
    chunks = [_chunk("a", "first passage"), _chunk("b", "second passage")]
    evidence = build_evidence(chunks)
    assert [e.id for e in evidence] == ["E1", "E2"]


def test_build_evidence_preserves_type_and_source():
    chunks = [
        _chunk("a", "local text", source="report.pdf", source_type="LOCAL_DOCUMENT", page=12),
        _chunk("b", "web text", source="https://example.com", source_type="WEB_SOURCE"),
    ]
    evidence = build_evidence(chunks)
    assert evidence[0].type == "LOCAL_DOCUMENT"
    assert evidence[0].source == "report.pdf"
    assert evidence[0].page == 12
    assert evidence[0].location == "page 12"
    assert evidence[1].type == "WEB_SOURCE"
    assert evidence[1].location is None


def test_build_evidence_dedups_near_identical_text():
    chunks = [
        _chunk("a", "The sky is blue."),
        _chunk("b", "  The   sky is blue.  "),  # same content, different whitespace/case-insensitive
        _chunk("c", "THE SKY IS BLUE."),
        _chunk("d", "Completely different content."),
    ]
    evidence = build_evidence(chunks)
    assert len(evidence) == 2
    assert evidence[0].text == "The sky is blue."
    assert evidence[1].text == "Completely different content."


def test_build_evidence_respects_context_size_cap():
    chunks = [_chunk(f"c{i}", "x" * 100) for i in range(10)]
    evidence = build_evidence(chunks, max_context_chars=250)
    # Should stop once the budget is exceeded, but keep at least the pieces that fit.
    assert 1 <= len(evidence) < 10
    assert sum(len(e.text) for e in evidence) <= 300  # allows the piece that pushed over budget


def test_build_evidence_always_keeps_at_least_one_item_even_if_it_exceeds_budget():
    chunks = [_chunk("a", "x" * 500)]
    evidence = build_evidence(chunks, max_context_chars=100)
    assert len(evidence) == 1


def test_build_evidence_empty_input_returns_empty_list():
    assert build_evidence([]) == []
