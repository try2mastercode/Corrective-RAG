import argparse
from pathlib import Path

from app.core.config import get_settings
from app.evaluation.dataset import load_dataset
from app.evaluation.reports import build_report
from app.evaluation.runners import run_crag
from scripts.evaluate import index_corpus


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quick CRAG latency/behavior benchmark (no RAGAS -- fast, for iteration)."
    )
    parser.add_argument("--dataset", default="data/evaluation/dataset.json")
    parser.add_argument("--corpus", default="data/evaluation/corpus")
    parser.add_argument("--vector-db-path", default="data/evaluation/eval_chroma_db")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings().model_copy(update={"vector_db_path": args.vector_db_path})

    print(f"Indexing corpus from {args.corpus} ...")
    index_corpus(Path(args.corpus), args.vector_db_path, settings)

    questions = load_dataset(args.dataset)
    if args.limit:
        questions = questions[: args.limit]

    crag_records = []
    for i, q in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] {q.question}")
        crag_records.append(run_crag(q, settings))

    report = build_report([], crag_records, {}, {})

    print()
    print(f"Questions:                 {report['dataset_size']}")
    print(
        f"CRAG latency:              avg={report['latency']['crag_avg']:.2f}s "
        f"p50={report['latency']['crag_p50']:.2f}s p95={report['latency']['crag_p95']:.2f}s"
    )
    print(f"Avg retrieval rounds:      {report['average_retrieval_rounds']:.2f}")
    print(f"Rewrite rate:              {report['rewrite_rate']:.0%}")
    print(f"Web fallback rate:         {report['web_fallback_rate']:.0%}")
    print(f"Answer correction rate:    {report['answer_correction_rate']:.0%}")
    print(f"Insufficient evidence rate:{report['insufficient_evidence_rate']:.0%}")


if __name__ == "__main__":
    main()
