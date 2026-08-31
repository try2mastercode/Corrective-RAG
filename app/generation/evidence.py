from app.core.models import Evidence, RetrievedChunk


def _normalize_for_dedup(text: str) -> str:
    return " ".join(text.split()).lower()


def _location(chunk: RetrievedChunk) -> str | None:
    page = chunk.metadata.get("page")
    return f"page {page}" if page else None


def build_evidence(chunks: list[RetrievedChunk], max_context_chars: int = 8000) -> list[Evidence]:
    """Normalize retrieved/corrected chunks into a stable evidence layer: dedup near-identical
    passages, assign stable E1/E2/... IDs, and cap total evidence text so the prompt doesn't grow
    unbounded. Chunks are assumed to already be ranked (best local matches first, then any web
    fallback results) by the correction controller -- this function preserves that order rather
    than re-ranking, since cross-source score blending (vector similarity vs. web search rank)
    isn't solved here (see PROGRESS.md)."""
    seen_normalized: set[str] = set()
    evidence: list[Evidence] = []
    total_chars = 0

    for chunk in chunks:
        normalized = _normalize_for_dedup(chunk.text)
        if normalized in seen_normalized:
            continue

        if evidence and total_chars + len(chunk.text) > max_context_chars:
            # Don't stop entirely -- a smaller, still-useful chunk ranked further down might
            # still fit even though this one doesn't.
            continue

        seen_normalized.add(normalized)
        total_chars += len(chunk.text)
        evidence.append(
            Evidence(
                id=f"E{len(evidence) + 1}",
                type=chunk.source_type,
                source=chunk.source,
                location=_location(chunk),
                page=chunk.metadata.get("page"),
                text=chunk.text,
            )
        )

    return evidence
