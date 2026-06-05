import os
import re
import math
from html import escape
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from elasticsearch import Elasticsearch

DEFAULT_ES_URL = "http://localhost:9200"
DEFAULT_INDEX = "bluesky_posts"
HIGHLIGHT_START = "___BLUESKY_HIGHLIGHT_START___"
HIGHLIGHT_END = "___BLUESKY_HIGHLIGHT_END___"

# Extra-credit: snippet window and scoring constants
SNIPPET_WINDOW = 40        # tokens on each side of the best hit
SNIPPET_MAX_CHARS = 280    # hard cap for displayed snippet
RECENCY_HALF_LIFE_DAYS = 30  # days after which recency contribution halves


@dataclass
class SearchResult:
        total: int
        took_ms: int | None
        results: list[dict[str, Any]]
        error: str | None = None


def get_client() -> Elasticsearch:
        es_url = os.getenv("ELASTICSEARCH_URL", DEFAULT_ES_URL)
        return Elasticsearch(es_url)


def get_index_name() -> str:
        return os.getenv("BLUESKY_INDEX", DEFAULT_INDEX)


def _base_highlight() -> dict[str, Any]:
        return {
                    "pre_tags": [HIGHLIGHT_START],
                    "post_tags": [HIGHLIGHT_END],
                    "fields": {
                                    "text": {"fragment_size": 220, "number_of_fragments": 1},
                                    "external_title": {"fragment_size": 160, "number_of_fragments": 1},
                    },
        }


def _query_for_mode(query: str, mode: str) -> dict[str, Any]:
        fields = ["text^2", "external_title^3"]

    if mode == "phrase":
                return {
                                "multi_match": {
                                                    "query": query,
                                                    "fields": ["text", "external_title"],
                                                    "type": "phrase",
                                }
                }

    if mode == "fuzzy":
                return {
                                "multi_match": {
                                                    "query": query,
                                                    "fields": fields,
                                                    "fuzziness": "AUTO",
                                }
                }

    if mode == "title":
                return {
                                "bool": {
                                                    "should": [
                                                                            {"match": {"external_title": {"query": query, "boost": 4}}},
                                                                            {"match": {"text": {"query": query, "boost": 1}}},
                                                    ],
                                                    "minimum_should_match": 1,
                                }
                }

    return {
                "multi_match": {
                                "query": query,
                                "fields": fields,
                                "type": "best_fields",
                }
    }


def build_search_body(
        query: str,
        mode: str = "standard",
        author: str = "",
        has_url: bool = False,
        date_from: str = "",
        date_to: str = "",
        sort: str = "relevance",
        page: int = 1,
        page_size: int = 10,
        w_relevance: float = 1.0,
        w_time: float = 0.0,
) -> dict[str, Any]:
        filters: list[dict[str, Any]] = []

    if author:
                filters.append({"term": {"author": author}})

    if has_url:
                filters.append({"exists": {"field": "url"}})

    date_range: dict[str, str] = {}
    if date_from:
                date_range["gte"] = date_from
            if date_to:
                        date_range["lte"] = date_to
                    if date_range:
                                filters.append({"range": {"created_at": date_range}})

    query_body: dict[str, Any]
    if query:
                query_body = {
                                "bool": {
                                                    "must": [_query_for_mode(query, mode)],
                                                    "filter": filters,
                                }
                }
else:
            query_body = {"bool": {"must": [{"match_all": {}}], "filter": filters}}

    body: dict[str, Any] = {
                "query": query_body,
                "highlight": _base_highlight(),
                "from": max(page - 1, 0) * page_size,
                "size": page_size,
                "track_total_hits": True,
    }

    # Extra-credit: weighted combination sort (relevance + time)
    if sort == "combined" and w_time > 0:
                # Use a script-based score that blends ES relevance with recency
                half_life_ms = RECENCY_HALF_LIFE_DAYS * 86400 * 1000
                decay_scale = f"{RECENCY_HALF_LIFE_DAYS}d"
                body["query"] = {
                    "function_score": {
                        "query": query_body,
                        "functions": [
                            {
                                "gauss": {
                                    "created_at": {
                                        "origin": "now",
                                        "scale": decay_scale,
                                        "decay": 0.5,
                                    }
                                },
                                "weight": w_time,
                            }
                        ],
                        "score_mode": "sum",
                        "boost_mode": "sum",
                    }
                }
elif sort == "newest":
            body["sort"] = [{"created_at": {"order": "desc"}}, "_score"]

    return body


def _total_value(total: Any) -> int:
        if isinstance(total, dict):
                    return int(total.get("value", 0))
                return int(total or 0)


# ---------------------------------------------------------------------------
# Extra-credit: custom snippet generation algorithm
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[tuple[str, int, int]]:
        """Return list of (token, start, end) with start/end as char offsets."""
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _normalize(token: str) -> str:
        """Lowercase and strip punctuation for matching."""
    return re.sub(r"[^\w]", "", token).lower()


def _best_window(
        tokens: list[tuple[str, int, int]],
        query_terms: set[str],
        window: int = SNIPPET_WINDOW,
) -> tuple[int, int]:
        """
            Sliding-window algorithm: score each window of `window` tokens by the
                number of distinct query terms it contains (term density).  Ties broken
                    by how early the window appears.  Returns (start_char, end_char).
                        """
    n = len(tokens)
    if n == 0:
                return (0, 0)

    best_score = -1
    best_start = 0
    best_end = min(window, n) - 1

    # Count initial window
    window_terms: dict[str, int] = {}
    w = min(window, n)
    for i in range(w):
                t = _normalize(tokens[i][0])
                if t in query_terms:
                                window_terms[t] = window_terms.get(t, 0) + 1

            score = len(window_terms)
    if score > best_score:
                best_score = score
                best_start = 0
                best_end = w - 1

    # Slide window
    for right in range(w, n):
                left = right - w
                # Add right token
                t_right = _normalize(tokens[right][0])
                if t_right in query_terms:
                                window_terms[t_right] = window_terms.get(t_right, 0) + 1
                            # Remove left token that just left the window
                            t_left = _normalize(tokens[left][0])
        if t_left in query_terms:
                        cnt = window_terms.get(t_left, 0) - 1
                        if cnt <= 0:
                                            window_terms.pop(t_left, None)
        else:
                window_terms[t_left] = cnt

        score = len(window_terms)
        if score > best_score:
                        best_score = score
                        best_start = left + 1
                        best_end = right

    start_char = tokens[best_start][1]
    end_char = tokens[best_end][2]
    return (start_char, end_char)


def _mark_terms(text: str, query_terms: set[str]) -> str:
        """Wrap query-term occurrences in <mark> tags (case-insensitive)."""
    if not query_terms:
                return escape(text)

    pattern = r"\b(" + "|".join(re.escape(t) for t in sorted(query_terms, key=len, reverse=True)) + r")\b"
    parts: list[str] = []
    last = 0
    for m in re.finditer(pattern, text, re.IGNORECASE):
                parts.append(escape(text[last:m.start()]))
        parts.append(f"<mark>{escape(m.group())}</mark>")
        last = m.end()
    parts.append(escape(text[last:]))
    return "".join(parts)


def _custom_snippet(text: str, query: str, max_chars: int = SNIPPET_MAX_CHARS) -> str:
        """
            Extra-credit snippet algorithm:
                1. Tokenize the document text.
                    2. Find the window of tokens with highest query-term density.
                        3. Extract that window, trim to max_chars, add ellipsis as needed.
                            4. Highlight query terms with <mark>.
                                """
    if not text:
                return ""

    query_terms: set[str] = {_normalize(w) for w in query.split() if w.strip()} if query else set()

    tokens = _tokenize(text)
    if not tokens:
                return escape(text[:max_chars])

    if query_terms:
                start_char, end_char = _best_window(tokens, query_terms)
else:
        start_char, end_char = (0, min(len(text), max_chars))

    # Expand a little around the window boundary to avoid cutting mid-word
    snippet_text = text[start_char:end_char]

    # Trim to max_chars
    if len(snippet_text) > max_chars:
                snippet_text = snippet_text[:max_chars - 1]

    prefix = "..." if start_char > 0 else ""
    suffix = "..." if end_char < len(text) else ""

    marked = _mark_terms(snippet_text, query_terms)
    return f"{prefix}{marked}{suffix}"


# ---------------------------------------------------------------------------
# Legacy helper (kept for backward compatibility, no longer primary)
# ---------------------------------------------------------------------------

def _safe_highlight(value: str) -> str:
        escaped = escape(value)
    return (
                escaped.replace(HIGHLIGHT_START, "<mark>")
                .replace(HIGHLIGHT_END, "</mark>")
    )


def _snippet(source: dict[str, Any], highlight: dict[str, list[str]], query: str = "") -> str:
        """
            Extra-credit: use our own snippet algorithm on the full post text.
                Falls back gracefully if text is missing.
                    """
    text = source.get("text") or ""
    return _custom_snippet(text, query)


# ---------------------------------------------------------------------------
# Recency score helper (used for post-retrieval combined ranking)
# ---------------------------------------------------------------------------

def _recency_score(created_at: str) -> float:
        """
            Returns a score in [0, 1] based on how recent the post is.
                Uses exponential decay with RECENCY_HALF_LIFE_DAYS half-life.
                    """
    try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_days = max((now - dt).total_seconds() / 86400, 0)
                return math.exp(-math.log(2) * age_days / RECENCY_HALF_LIFE_DAYS)
except Exception:
        return 0.0


def search_posts(
        query: str,
        mode: str = "standard",
        author: str = "",
        has_url: bool = False,
        date_from: str = "",
        date_to: str = "",
        sort: str = "relevance",
        page: int = 1,
        page_size: int = 10,
        w_relevance: float = 1.0,
        w_time: float = 0.0,
) -> SearchResult:
        es = get_client()
    index_name = get_index_name()
    body = build_search_body(
                query=query,
                mode=mode,
                author=author,
                has_url=has_url,
                date_from=date_from,
                date_to=date_to,
                sort=sort,
                page=page,
                page_size=page_size,
                w_relevance=w_relevance,
                w_time=w_time,
    )

    try:
                response = es.search(index=index_name, body=body)
except Exception as exc:
        return SearchResult(total=0, took_ms=None, results=[], error=str(exc))

    hits = response.get("hits", {})
    results = []
    raw_hits = hits.get("hits", [])

    # Extra-credit: client-side combined re-ranking when sort == "combined"
    # Normalise ES scores then blend with recency
    if sort == "combined" and raw_hits:
                max_es = max((h.get("_score") or 0.0) for h in raw_hits) or 1.0
                for hit in raw_hits:
                                src = hit.get("_source", {})
                                es_norm = (hit.get("_score") or 0.0) / max_es
                                rec = _recency_score(src.get("created_at", ""))
                                hit["_combined_score"] = w_relevance * es_norm + w_time * rec
                            raw_hits.sort(key=lambda h: h["_combined_score"], reverse=True)

    for hit in raw_hits:
                source = hit.get("_source", {})
        highlight = hit.get("highlight", {})
        title_highlights = highlight.get("external_title") or []

        combined = hit.get("_combined_score")
        display_score = combined if combined is not None else hit.get("_score")

        results.append(
                        {
                                            "id": hit.get("_id"),
                                            "score": display_score,
                                            "text": source.get("text", ""),
                                            # Extra-credit: our own snippet, not ES-generated
                                            "snippet": _snippet(source, highlight, query),
                                            "external_title": source.get("external_title") or "",
                                            "external_title_highlight": _safe_highlight(title_highlights[0]) if title_highlights else "",
                                            "author": source.get("author", ""),
                                            "created_at": source.get("created_at", ""),
                                            "uri": source.get("uri", ""),
                                            "url": source.get("url", ""),
                        }
        )

    return SearchResult(
                total=_total_value(hits.get("total")),
                took_ms=response.get("took"),
                results=results,
    )


def health_status() -> dict[str, Any]:
        es = get_client()
    index_name = get_index_name()
    status: dict[str, Any] = {
                "es_url": os.getenv("ELASTICSEARCH_URL", DEFAULT_ES_URL),
                "index": index_name,
                "connected": False,
                "index_exists": False,
                "document_count": None,
                "error": None,
    }

    try:
                status["connected"] = bool(es.ping())
        status["index_exists"] = bool(es.indices.exists(index=index_name))
        if status["index_exists"]:
                        count_response = es.count(index=index_name)
                        status["document_count"] = count_response.get("count", 0)
except Exception as exc:
        status["error"] = str(exc)

    return status
