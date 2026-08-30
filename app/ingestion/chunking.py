import hashlib
import re

from app.core.models import Chunk, ChunkMetadata, utc_now_iso
from app.ingestion.loaders import LoadedDocument

# Rough token approximation: ~4 characters per token for English text.
CHARS_PER_TOKEN = 4

_SPLIT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _split_text(text: str, chunk_size_chars: int) -> list[str]:
    """Recursively split text on decreasing granularity separators, keeping
    pieces under chunk_size_chars where possible."""
    if len(text) <= chunk_size_chars:
        return [text] if text.strip() else []

    for separator in _SPLIT_SEPARATORS:
        if separator == "":
            # Last resort: hard split by character count.
            return [text[i : i + chunk_size_chars] for i in range(0, len(text), chunk_size_chars)]

        if separator in text:
            parts = text.split(separator)
            chunks: list[str] = []
            current = ""
            for part in parts:
                candidate = current + separator + part if current else part
                if len(candidate) <= chunk_size_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    if len(part) > chunk_size_chars:
                        chunks.extend(_split_text(part, chunk_size_chars))
                        current = ""
                    else:
                        current = part
            if current:
                chunks.append(current)
            return [c for c in chunks if c.strip()]

    return [text]


def _add_overlap(pieces: list[str], overlap_chars: int) -> list[str]:
    if overlap_chars <= 0 or len(pieces) <= 1:
        return pieces
    overlapped = [pieces[0]]
    for i in range(1, len(pieces)):
        prev_tail = pieces[i - 1][-overlap_chars:]
        overlapped.append(prev_tail + pieces[i])
    return overlapped


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compute_chunk_id(document_id: str, page: int | None, index: int, text: str) -> str:
    digest_input = f"{document_id}:{page}:{index}:{text}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()[:16]


def chunk_document(
    doc: LoadedDocument,
    chunk_size_tokens: int = 600,
    overlap_tokens: int = 100,
) -> list[Chunk]:
    chunk_size_chars = chunk_size_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    chunks: list[Chunk] = []
    seen_hashes: set[str] = set()
    index = 0

    for page in doc.pages:
        normalized = normalize_text(page.text)
        if not normalized:
            continue

        pieces = _split_text(normalized, chunk_size_chars)
        pieces = _add_overlap(pieces, overlap_chars)

        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue

            text_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
            if text_hash in seen_hashes:
                continue
            seen_hashes.add(text_hash)

            chunk_id = compute_chunk_id(doc.document_id, page.page, index, piece)
            chunks.append(
                Chunk(
                    text=piece,
                    metadata=ChunkMetadata(
                        document_id=doc.document_id,
                        source=doc.source,
                        title=doc.title,
                        page=page.page,
                        chunk_id=chunk_id,
                        created_at=utc_now_iso(),
                        hash=text_hash,
                    ),
                )
            )
            index += 1

    return chunks
