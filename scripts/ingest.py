import argparse
import sys
from pathlib import Path

from app.core.dependencies import build_embedding_provider, build_vector_store
from app.ingestion.indexing import index_document
from app.ingestion.loaders import SUPPORTED_EXTENSIONS


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and index local documents.")
    parser.add_argument("path", help="File or directory of documents to ingest")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Path not found: {path}", file=sys.stderr)
        sys.exit(1)

    if path.is_dir():
        files = [p for p in path.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    else:
        files = [path]

    if not files:
        print("No supported documents found.")
        return

    embeddings = build_embedding_provider()
    store = build_vector_store()

    for file_path in files:
        result = index_document(file_path, embeddings, store)
        print(f"Indexed {result['source']}: {result['chunks_indexed']} chunks (document_id={result['document_id']})")


if __name__ == "__main__":
    main()
