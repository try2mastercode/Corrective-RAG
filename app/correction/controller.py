import logging

from app.core.config import Settings
from app.core.models import CorrectiveRetrievalResult, GradedChunk, RetrievedChunk, RetrievalRound
from app.correction.query_rewriter import rewrite_query
from app.llm.base import LLMClient
from app.retrieval.grader import calculate_retrieval_quality, grade_chunks
from app.retrieval.retriever import Retriever
from app.web.search import compute_web_chunk_id, web_search


logger = logging.getLogger(__name__)


def compute_retrieval_status(evidence: list, correction: CorrectiveRetrievalResult) -> str:
    if not evidence:
        return "NO_RESULTS"
    if correction.web_used:
        return "WEB_FALLBACK"
    return correction.final_quality.decision


def _quality(settings: Settings, graded: list[GradedChunk]):
    return calculate_retrieval_quality(
        graded,
        weight_mean=settings.quality_weight_mean,
        weight_best=settings.quality_weight_best,
        weight_relevant_ratio=settings.quality_weight_relevant_ratio,
        high_threshold=settings.retrieval_quality_high_threshold,
        medium_threshold=settings.retrieval_quality_medium_threshold,
    )


def run_corrective_retrieval(
    question: str,
    retriever: Retriever,
    llm: LLMClient,
    settings: Settings,
) -> CorrectiveRetrievalResult:
    """Retrieve -> grade -> (if weak) rewrite -> retrieve again -> grade again, bounded by
    MAX_RETRIEVAL_ROUNDS. Each round's STRONG/WEAK decision is based on that round's own
    retrieval only (matching the spec's per-round branching); the final evidence set and its
    reported quality are the union of everything graded across all rounds, since that's what
    actually gets passed to answer generation."""
    graded_by_id: dict[str, GradedChunk] = {}
    rounds: list[RetrievalRound] = []
    rewrites = []
    seen_queries = {question.strip().lower()}
    query_for_retrieval = question
    round_num = 1

    while True:
        retrieved = retriever.retrieve(query_for_retrieval, top_k=settings.top_k)
        new_chunks = [c for c in retrieved if c.chunk_id not in graded_by_id]

        if new_chunks:
            newly_graded = grade_chunks(question, new_chunks, llm, max_retries=settings.grader_max_retries)
            for gc in newly_graded:
                graded_by_id[gc.chunk.chunk_id] = gc

        round_graded = [graded_by_id[c.chunk_id] for c in retrieved]
        round_quality = _quality(settings, round_graded)
        rounds.append(RetrievalRound(round=round_num, query=query_for_retrieval, quality=round_quality))
        logger.info("retrieval round %d (%r): decision=%s", round_num, query_for_retrieval, round_quality.decision)

        if round_quality.decision == "HIGH" or round_num >= settings.max_retrieval_rounds:
            break

        rewrite = rewrite_query(question, llm, max_retries=settings.grader_max_retries)
        rewrites.append(rewrite)

        normalized = rewrite.rewritten_query.strip().lower()
        if normalized in seen_queries:
            logger.info("rewrite produced a repeated/equivalent query; stopping correction loop")
            break

        seen_queries.add(normalized)
        query_for_retrieval = rewrite.rewritten_query
        round_num += 1

    final_graded = sorted(graded_by_id.values(), key=lambda gc: gc.grade.score, reverse=True)
    final_chunks = [gc.chunk for gc in final_graded if gc.grade.label != "IRRELEVANT"]
    final_quality = _quality(settings, list(graded_by_id.values()))

    return CorrectiveRetrievalResult(
        final_chunks=final_chunks,
        rounds=rounds,
        rewrites=rewrites,
        final_quality=final_quality,
    )


def _web_result_to_chunk(result) -> RetrievedChunk:
    text = f"{result.title}\n{result.snippet}".strip()
    return RetrievedChunk(
        chunk_id=compute_web_chunk_id(result.url),
        text=text,
        # Not a vector-similarity score (web results aren't embedded/ranked that way) --
        # a neutral placeholder; grading below is what actually decides relevance.
        score=0.5,
        source=result.url,
        metadata={"title": result.title, "retrieved_at": result.retrieved_at},
        source_type="WEB_SOURCE",
    )


def apply_web_fallback(
    question: str,
    correction: CorrectiveRetrievalResult,
    llm: LLMClient,
    settings: Settings,
) -> CorrectiveRetrievalResult:
    """If local retrieval is still not HIGH after corrective retrieval and web fallback is
    enabled, search the web, grade the results against the original question, and append any
    non-IRRELEVANT results to the evidence set. Local evidence always comes first -- web search
    is a supplement for when local retrieval fell short, not a replacement for it. Never raises:
    a search failure just means no web evidence gets added."""
    if not settings.web_search_enabled or correction.final_quality.decision == "HIGH":
        return correction

    web_results = web_search(
        question,
        provider=settings.web_search_provider,
        max_results=settings.web_search_max_results,
        timeout=settings.web_search_timeout,
    )

    if not web_results:
        return correction.model_copy(update={"web_search_triggered": True})

    web_chunks = [_web_result_to_chunk(r) for r in web_results]
    graded_web = grade_chunks(question, web_chunks, llm, max_retries=settings.grader_max_retries)
    relevant_web = sorted(
        (gc for gc in graded_web if gc.grade.label != "IRRELEVANT"),
        key=lambda gc: gc.grade.score,
        reverse=True,
    )
    relevant_web_chunks = [gc.chunk for gc in relevant_web]

    logger.info(
        "web fallback: %d results fetched, %d graded relevant",
        len(web_results),
        len(relevant_web_chunks),
    )

    return correction.model_copy(
        update={
            "final_chunks": correction.final_chunks + relevant_web_chunks,
            "web_search_triggered": True,
            "web_used": bool(relevant_web_chunks),
            "web_results": web_results,
        }
    )
