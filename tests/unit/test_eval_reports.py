from app.evaluation.reports import _percentile, build_report, format_report_markdown
from app.evaluation.runners import RunRecord


def _record(**overrides) -> RunRecord:
    defaults = dict(
        question_id="q1",
        category="easy",
        question="Q?",
        ground_truth="A",
        answer="A",
        contexts=["some context"],
        latency_seconds=1.0,
        retrieval_status="HIGH",
        grounding_status="SUPPORTED",
        retrieval_rounds=1,
        rewrite_used=False,
        web_used=False,
        answer_corrected=False,
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


def test_percentile_of_empty_list_is_zero():
    assert _percentile([], 0.5) == 0.0


def test_percentile_matches_known_values():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 0.5) == 30.0
    assert _percentile(values, 0.0) == 10.0
    assert _percentile(values, 1.0) == 50.0


def test_build_report_computes_rates_correctly():
    crag_records = [
        _record(question_id="q1", rewrite_used=True, latency_seconds=2.0),
        _record(question_id="q2", web_used=True, latency_seconds=4.0),
        _record(question_id="q3", answer_corrected=True, latency_seconds=6.0),
        _record(question_id="q4", retrieval_status="NO_RESULTS", latency_seconds=1.0),
    ]
    report = build_report([], crag_records, {}, {})

    assert report["dataset_size"] == 4
    assert report["rewrite_rate"] == 0.25
    assert report["web_fallback_rate"] == 0.25
    assert report["answer_correction_rate"] == 0.25
    assert report["insufficient_evidence_rate"] == 0.25
    assert report["latency"]["crag_avg"] == 3.25


def test_build_report_computes_improvement_pct():
    baseline_ragas = {"faithfulness": 0.5}
    crag_ragas = {"faithfulness": 0.75}
    report = build_report([_record()], [_record()], baseline_ragas, crag_ragas)
    assert report["improvement_pct"]["faithfulness"] == 50.0


def test_build_report_handles_empty_records_gracefully():
    report = build_report([], [], {}, {})
    assert report["dataset_size"] == 0
    assert report["rewrite_rate"] == 0.0
    assert report["latency"]["crag_avg"] == 0.0


def test_format_report_markdown_includes_key_sections():
    report = build_report([_record()], [_record(rewrite_used=True)], {"faithfulness": 0.8}, {"faithfulness": 0.9})
    markdown = format_report_markdown(report)
    assert "# CRAG Evaluation Report" in markdown
    assert "faithfulness" in markdown
    assert "Query rewrite rate" in markdown
    assert "Failure / Correction Examples" in markdown
