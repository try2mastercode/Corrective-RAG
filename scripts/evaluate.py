import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.core.dependencies import build_embedding_provider
from app.evaluation.dataset import load_dataset
from app.evaluation.ragas_runner import run_ragas_evaluation
from app.evaluation.reports import build_report, format_report_markdown
from app.evaluation.runners import run_baseline, run_crag
from app.ingestion.indexing import index_document
from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.retrieval.vector_store import ChromaVectorStore


def index_corpus(corpus_dir: Path, vector_db_path: str, settings) -> None:
    embeddings = build_embedding_provider(settings)
    store = ChromaVectorStore(vector_db_path, embeddings.dimension, embeddings.model_name)
    for file_path in sorted(corpus_dir.iterdir()):
        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            index_document(file_path, embeddings, store)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAGAS baseline-vs-CRAG evaluation.")
    parser.add_argument("--dataset", default="data/evaluation/dataset.json")
    parser.add_argument("--corpus", default="data/evaluation/corpus")
    parser.add_argument("--output", default="data/evaluation/report.md")
    parser.add_argument("--vector-db-path", default="data/evaluation/eval_chroma_db")
    parser.add_argument("--web-fallback", action="store_true", help="Enable web search fallback for the CRAG run")
    parser.add_argument("--no-ragas", action="store_true", help="Skip RAGAS metrics (faster, latency/rates only)")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N questions")
    args = parser.parse_args()

    settings = get_settings().model_copy(
        update={
            "vector_db_path": args.vector_db_path,
            "web_search_enabled": args.web_fallback or get_settings().web_search_enabled,
        }
    )

    print(f"Indexing corpus from {args.corpus} into {args.vector_db_path} ...")
    index_corpus(Path(args.corpus), args.vector_db_path, settings)

    questions = load_dataset(args.dataset)
    if args.limit:
        questions = questions[: args.limit]
    print(f"Loaded {len(questions)} evaluation questions.")

    baseline_records = []
    crag_records = []
    for i, q in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] baseline: {q.question}")
        baseline_records.append(run_baseline(q, settings))
        print(f"[{i}/{len(questions)}] crag:     {q.question}")
        crag_records.append(run_crag(q, settings, web_fallback=args.web_fallback))

    baseline_ragas: dict = {}
    crag_ragas: dict = {}
    if not args.no_ragas:
        print("Running RAGAS metrics (baseline) ...")
        baseline_ragas = run_ragas_evaluation(baseline_records, settings)
        print("Running RAGAS metrics (CRAG) ...")
        crag_ragas = run_ragas_evaluation(crag_records, settings)

    report = build_report(baseline_records, crag_records, baseline_ragas, crag_ragas)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_report_markdown(report), encoding="utf-8")

    json_path = output_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "report": report,
                "baseline_records": [r.model_dump() for r in baseline_records],
                "crag_records": [r.model_dump() for r in crag_records],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Report written to {output_path} and {json_path}")


if __name__ == "__main__":
    main()
