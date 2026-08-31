from statistics import mean

from app.evaluation.runners import RunRecord


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _select_failure_examples(records: list[RunRecord], limit: int = 5) -> list[dict]:
    """Prioritize examples that actually exercised correction machinery -- these are the
    interesting cases for debugging/learning, per todo.md section 22."""
    interesting = [
        r
        for r in records
        if r.retrieval_status in ("LOW", "MEDIUM", "NO_RESULTS")
        or r.rewrite_used
        or r.web_used
        or r.answer_corrected
    ]
    selected = interesting[:limit] if interesting else records[:limit]
    return [
        {
            "question_id": r.question_id,
            "category": r.category,
            "question": r.question,
            "ground_truth": r.ground_truth,
            "answer": r.answer,
            "retrieval_status": r.retrieval_status,
            "grounding_status": r.grounding_status,
            "retrieval_rounds": r.retrieval_rounds,
            "rewrite_used": r.rewrite_used,
            "web_used": r.web_used,
            "answer_corrected": r.answer_corrected,
        }
        for r in selected
    ]


def build_report(
    baseline_records: list[RunRecord],
    crag_records: list[RunRecord],
    baseline_ragas: dict[str, float],
    crag_ragas: dict[str, float],
) -> dict:
    dataset_size = len(crag_records) or len(baseline_records)
    baseline_latencies = [r.latency_seconds for r in baseline_records]
    crag_latencies = [r.latency_seconds for r in crag_records]

    improvement_pct = {}
    for metric in sorted(set(baseline_ragas) & set(crag_ragas)):
        b, c = baseline_ragas[metric], crag_ragas[metric]
        improvement_pct[metric] = ((c - b) / b * 100) if b else None

    n = len(crag_records)
    return {
        "dataset_size": dataset_size,
        "baseline_metrics": baseline_ragas,
        "crag_metrics": crag_ragas,
        "improvement_pct": improvement_pct,
        "latency": {
            "baseline_avg": mean(baseline_latencies) if baseline_latencies else 0.0,
            "baseline_p50": _percentile(baseline_latencies, 0.5),
            "baseline_p95": _percentile(baseline_latencies, 0.95),
            "crag_avg": mean(crag_latencies) if crag_latencies else 0.0,
            "crag_p50": _percentile(crag_latencies, 0.5),
            "crag_p95": _percentile(crag_latencies, 0.95),
        },
        "average_retrieval_rounds": mean([r.retrieval_rounds for r in crag_records]) if crag_records else 0.0,
        "rewrite_rate": (sum(1 for r in crag_records if r.rewrite_used) / n) if n else 0.0,
        "web_fallback_rate": (sum(1 for r in crag_records if r.web_used) / n) if n else 0.0,
        "answer_correction_rate": (sum(1 for r in crag_records if r.answer_corrected) / n) if n else 0.0,
        "insufficient_evidence_rate": (
            sum(1 for r in crag_records if r.retrieval_status == "NO_RESULTS") / n
        )
        if n
        else 0.0,
        "failure_examples": _select_failure_examples(crag_records),
    }


def format_report_markdown(report: dict) -> str:
    lines = ["# CRAG Evaluation Report", ""]
    lines.append(f"Dataset size: **{report['dataset_size']}**")
    lines.append("")

    lines.append("## RAGAS Metrics: Baseline vs CRAG")
    lines.append("")
    lines.append("| Metric | Baseline | CRAG | Improvement |")
    lines.append("|---|---|---|---|")
    all_metrics = sorted(set(report["baseline_metrics"]) | set(report["crag_metrics"]))
    if not all_metrics:
        lines.append("| _(no RAGAS metrics available)_ | - | - | - |")
    for metric in all_metrics:
        b = report["baseline_metrics"].get(metric)
        c = report["crag_metrics"].get(metric)
        imp = report["improvement_pct"].get(metric)
        b_str = f"{b:.3f}" if isinstance(b, (int, float)) else "n/a"
        c_str = f"{c:.3f}" if isinstance(c, (int, float)) else "n/a"
        imp_str = f"{imp:+.1f}%" if isinstance(imp, (int, float)) else "n/a"
        lines.append(f"| {metric} | {b_str} | {c_str} | {imp_str} |")
    lines.append("")

    lat = report["latency"]
    lines.append("## Latency")
    lines.append("")
    lines.append("| | Baseline | CRAG |")
    lines.append("|---|---|---|")
    lines.append(f"| Average | {lat['baseline_avg']:.2f}s | {lat['crag_avg']:.2f}s |")
    lines.append(f"| p50 | {lat['baseline_p50']:.2f}s | {lat['crag_p50']:.2f}s |")
    lines.append(f"| p95 | {lat['baseline_p95']:.2f}s | {lat['crag_p95']:.2f}s |")
    lines.append("")

    lines.append("## CRAG Behavior")
    lines.append("")
    lines.append(f"- Average retrieval rounds: {report['average_retrieval_rounds']:.2f}")
    lines.append(f"- Query rewrite rate: {report['rewrite_rate']:.0%}")
    lines.append(f"- Web fallback rate: {report['web_fallback_rate']:.0%}")
    lines.append(f"- Answer correction rate: {report['answer_correction_rate']:.0%}")
    lines.append(f"- Insufficient-evidence rate: {report['insufficient_evidence_rate']:.0%}")
    lines.append("")

    lines.append("## Failure / Correction Examples")
    lines.append("")
    for ex in report["failure_examples"]:
        lines.append(f"### {ex['question_id']} ({ex['category']})")
        lines.append(f"- Question: {ex['question']}")
        lines.append(f"- Ground truth: {ex['ground_truth']}")
        lines.append(f"- Answer: {ex['answer']}")
        lines.append(
            f"- retrieval_status={ex['retrieval_status']}, grounding_status={ex['grounding_status']}, "
            f"rounds={ex['retrieval_rounds']}, rewrite_used={ex['rewrite_used']}, "
            f"web_used={ex['web_used']}, answer_corrected={ex['answer_corrected']}"
        )
        lines.append("")

    return "\n".join(lines)
