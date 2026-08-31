import asyncio
import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import Settings, get_settings
from app.core.dependencies import build_embedding_provider, build_vector_store
from app.core.models import DocumentInfo
from app.ingestion.indexing import index_document
from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.retrieval.vector_store import ChromaVectorStore

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
RAW_DATA_DIR = Path("data/raw")

# Windows reserves these device names regardless of extension (CON, CON.txt, con.PDF, ... are
# all reserved) -- writing to one behaves specially at the OS level instead of creating a
# normal file.
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if Path(name).stem.upper() in _WINDOWS_RESERVED_NAMES:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


def _resolve_destination(safe_name: str, content: bytes) -> Path:
    """Pick a destination path for `safe_name`, disambiguating with a content-hash prefix if a
    file with that name already exists but holds different content -- prevents concurrent or
    same-named-but-different uploads from silently overwriting each other."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DATA_DIR / safe_name

    if dest.exists() and dest.read_bytes() != content:
        content_hash = hashlib.sha256(content).hexdigest()[:8]
        safe_name = f"{content_hash}_{safe_name}"
        dest = RAW_DATA_DIR / safe_name

    resolved = dest.resolve()
    if RAW_DATA_DIR.resolve() not in resolved.parents and resolved != RAW_DATA_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid destination path")

    return dest


@router.post("/upload")
async def upload_document(file: UploadFile):
    safe_name = _sanitize_filename(file.filename or "")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    # Read in bounded chunks so an oversized upload is rejected without first buffering the
    # whole thing into memory.
    content = bytearray()
    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
    content = bytes(content)

    dest = _resolve_destination(safe_name, content)
    await asyncio.to_thread(dest.write_bytes, content)
    return {"filename": dest.name, "size_bytes": len(content)}


def _index_uploaded_document_sync(safe_name: str, settings: Settings) -> dict:
    path = RAW_DATA_DIR / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found; upload it first")

    embeddings = build_embedding_provider(settings)
    store = build_vector_store(settings)
    return index_document(path, embeddings, store)


@router.post("/index")
async def index_uploaded_document(filename: str):
    safe_name = _sanitize_filename(filename)
    settings = get_settings()
    # Embedding inference and the vector store write are synchronous/CPU-bound -- offload so a
    # large document doesn't block other concurrent requests.
    return await asyncio.to_thread(_index_uploaded_document_sync, safe_name, settings)


def _list_documents_sync(store: ChromaVectorStore) -> list[dict]:
    return store.list_documents()


@router.get("", response_model=list[DocumentInfo])
async def list_documents():
    store = build_vector_store()
    return await asyncio.to_thread(_list_documents_sync, store)


def _delete_document_sync(store: ChromaVectorStore, document_id: str) -> int:
    return store.delete_document(document_id)


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    store = build_vector_store()
    deleted = await asyncio.to_thread(_delete_document_sync, store, document_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": document_id, "chunks_deleted": deleted}
