import os
from html import escape
from dataclasses import dataclass
from typing import Any

from elasticsearch import Elasticsearch


DEFAULT_ES_URL = "http://localhost:9200"
DEFAULT_INDEX = "bluesky_posts"
HIGHLIGHT_START = "___BLUESKY_HIGHLIGHT_START___"
HIGHLIGHT_END = "___BLUESKY_HIGHLIGHT_END___"


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

    if sort == "newest":
        body["sort"] = [{"created_at": {"order": "desc"}}, "_score"]

    return body


def _total_value(total: Any) -> int:
    if isinstance(total, dict):
        return int(total.get("value", 0))
    return int(total or 0)


def _snippet(source: dict[str, Any], highlight: dict[str, list[str]]) -> str:
    text_hits = highlight.get("text") or []
    if text_hits:
        return _safe_highlight(text_hits[0])

    text = source.get("text") or ""
    if len(text) > 260:
        return escape(f"{text[:257]}...")
    return escape(text)


def _safe_highlight(value: str) -> str:
    escaped = escape(value)
    return (
        escaped.replace(HIGHLIGHT_START, "<mark>")
        .replace(HIGHLIGHT_END, "</mark>")
    )


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
    )

    try:
        response = es.search(index=index_name, body=body)
    except Exception as exc:
        return SearchResult(total=0, took_ms=None, results=[], error=str(exc))

    hits = response.get("hits", {})
    results = []
    for hit in hits.get("hits", []):
        source = hit.get("_source", {})
        highlight = hit.get("highlight", {})
        title_highlights = highlight.get("external_title") or []

        results.append(
            {
                "id": hit.get("_id"),
                "score": hit.get("_score"),
                "text": source.get("text", ""),
                "snippet": _snippet(source, highlight),
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
