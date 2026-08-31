# CRAG Evaluation Report

Dataset size: **2**

## RAGAS Metrics: Baseline vs CRAG

| Metric | Baseline | CRAG | Improvement |
|---|---|---|---|
| answer_relevancy | 0.953 | 0.942 | -1.1% |
| context_precision | 1.000 | 1.000 | +0.0% |
| context_recall | 1.000 | 1.000 | +0.0% |
| faithfulness | 1.000 | 1.000 | +0.0% |

## Latency

| | Baseline | CRAG |
|---|---|---|
| Average | 21.56s | 118.05s |
| p50 | 21.56s | 118.05s |
| p95 | 21.63s | 124.36s |

## CRAG Behavior

- Average retrieval rounds: 2.00
- Query rewrite rate: 100%
- Web fallback rate: 0%
- Answer correction rate: 0%
- Insufficient-evidence rate: 0%

## Failure / Correction Examples

### easy_01 (easy)
- Question: Who was the engineer who completed the Vantel Bridge?
- Ground truth: Rosalind Achebe
- Answer: Rosalind Achebe.
- retrieval_status=LOW, grounding_status=SUPPORTED, rounds=2, rewrite_used=True, web_used=False, answer_corrected=False

### easy_02 (easy)
- Question: In what year was the Corvane Observatory completed?
- Ground truth: 1988
- Answer: The Corvane Observatory was completed in 1988.
- retrieval_status=LOW, grounding_status=SUPPORTED, rounds=2, rewrite_used=True, web_used=False, answer_corrected=False
