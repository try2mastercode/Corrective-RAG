import hashlib
import logging

from ddgs import DDGS
from ddgs.exceptions import DDGSException

from app.core.models import WebSearchResult, utc_now_iso

logger = logging.getLogger(__name__)


def compute_web_chunk_id(url: str) -> str:
    return "web_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _duckduckgo_search(query: str, max_results: int, timeout: float) -> list[WebSearchResult]:
    try:
        raw_results = DDGS(timeout=timeout).text(query, max_results=max_results)
    except DDGSException as exc:
        logger.warning("duckduckgo search failed: %s", exc)
        return []
    except Exception:
        logger.exception("unexpected error during duckduckgo search")
        return []

    seen_urls: set[str] = set()
    results: list[WebSearchResult] = []
    for r in raw_results or []:
        url = (r.get("href") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            WebSearchResult(
                url=url,
                title=(r.get("title") or "").strip(),
                snippet=(r.get("body") or "").strip(),
                retrieved_at=utc_now_iso(),
            )
        )
    return results


def web_search(query: str, provider: str, max_results: int = 5, timeout: float = 10.0) -> list[WebSearchResult]:
    if provider == "duckduckgo":
        return _duckduckgo_search(query, max_results, timeout)

    logger.warning("unknown or unconfigured web search provider %r; skipping web fallback", provider)
    return []
