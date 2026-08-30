import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.dependencies import build_embedding_provider, build_vector_store
from app.core.models import DocumentInfo
from app.ingestion.indexing import index_document
from app.ingestion.loaders import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
RAW_DATA_DIR = Path("data/raw")


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


@router.post("/upload")
async def upload_document(file: UploadFile):
    safe_name = _sanitize_filename(file.filename or "")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DATA_DIR / safe_name

    resolved = dest.resolve()
    if RAW_DATA_DIR.resolve() not in resolved.parents and resolved != RAW_DATA_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid destination path")

    dest.write_bytes(content)
    return {"filename": safe_name, "size_bytes": len(content)}


@router.post("/index")
async def index_uploaded_document(filename: str):
    safe_name = _sanitize_filename(filename)
    path = RAW_DATA_DIR / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found; upload it first")

    settings = get_settings()
    embeddings = build_embedding_provider(settings)
    store = build_vector_store(settings)

    result = index_document(path, embeddings, store)
    return result


@router.get("", response_model=list[DocumentInfo])
async def list_documents():
    store = build_vector_store()
    return store.list_documents()


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    store = build_vector_store()
    deleted = store.delete_document(document_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": document_id, "chunks_deleted": deleted}
