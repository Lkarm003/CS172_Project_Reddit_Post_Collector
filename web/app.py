from flask import Flask, jsonify, render_template, request
from web.search_service import health_status, search_posts

VALID_MODES = {"standard", "fuzzy", "phrase", "title"}
VALID_SORTS = {"relevance", "newest", "combined"}
PAGE_SIZE = 10

W_MIN = 0.0
W_MAX = 5.0


def _float_param(value: str, default: float, lo: float = W_MIN, hi: float = W_MAX) -> float:
    try:
        v = float(value)
        return max(lo, min(hi, v))
    except (ValueError, TypeError):
        return default


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def home():
        status = health_status()
        return render_template(
            "search.html",
            status=status,
            query="",
            mode="standard",
            author="",
            has_url=False,
            date_from="",
            date_to="",
            sort="relevance",
            w_relevance=1.0,
            w_time=0.0,
        )

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        mode = request.args.get("mode", "standard")
        sort = request.args.get("sort", "relevance")
        author = request.args.get("author", "").strip()
        has_url = request.args.get("has_url") == "on"
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        # Extra-credit: combined-ranking weights
        w_relevance = _float_param(request.args.get("w_relevance", "1.0"), default=1.0)
        w_time = _float_param(request.args.get("w_time", "0.0"), default=0.0)

        try:
            page = max(int(request.args.get("page", "1")), 1)
        except ValueError:
            page = 1

        if mode not in VALID_MODES:
            mode = "standard"
        if sort not in VALID_SORTS:
            sort = "relevance"

        result = search_posts(
            query=query,
            mode=mode,
            author=author,
            has_url=has_url,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            page=page,
            page_size=PAGE_SIZE,
            w_relevance=w_relevance,
            w_time=w_time,
        )

        return render_template(
            "results.html",
            query=query,
            mode=mode,
            sort=sort,
            author=author,
            has_url=has_url,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=PAGE_SIZE,
            total=result.total,
            took_ms=result.took_ms,
            results=result.results,
            error=result.error,
            status=health_status(),
            w_relevance=w_relevance,
            w_time=w_time,
        )

    @app.route("/api/search")
    def api_search():
        query = request.args.get("q", "").strip()
        mode = request.args.get("mode", "standard")
        if mode not in VALID_MODES:
            mode = "standard"

        result = search_posts(query=query, mode=mode, page_size=10)
        return jsonify(
            {
                "total": result.total,
                "took_ms": result.took_ms,
                "results": result.results,
                "error": result.error,
            }
        )

    @app.route("/health")
    def health():
        return render_template("health.html", status=health_status())

    @app.route("/api/health")
    def api_health():
        return jsonify(health_status())

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)