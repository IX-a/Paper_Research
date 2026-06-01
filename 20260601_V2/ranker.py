import math
from datetime import datetime

W_POSITION = 0.30
W_KEYWORD = 0.25
W_MESH = 0.20
W_TIME = 0.15
W_JOURNAL = 0.10

TIME_DECAY = 0.1


def _tokenize(text: str) -> list[str]:
    return [t.strip().lower() for t in text.replace(",", " ").split() if len(t.strip()) > 1]


def _position_score(index: int, total: int) -> float:
    return 1.0 - (index / max(total, 1))


def _keyword_score(query_tokens: list[str], title: str, abstract: str) -> float:
    if not query_tokens:
        return 0.0
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    total = 0.0
    for token in query_tokens:
        if token in title_lower:
            total += 2.0
        if token in abstract_lower:
            total += 1.0
    return total / len(query_tokens)


def _mesh_score(query_tokens: list[str], mesh_terms: list[str]) -> float:
    if not query_tokens or not mesh_terms:
        return 0.0
    mesh_lower = [m.lower() for m in mesh_terms]
    matches = 0
    for token in query_tokens:
        for mesh in mesh_lower:
            if token in mesh:
                matches += 1
                break
    return min(matches / len(query_tokens), 1.0)


def _time_score(year: str | None) -> float:
    current_year = datetime.now().year
    try:
        pub_year = int(year) if year else current_year - 5
    except ValueError:
        pub_year = current_year - 5
    delta = max(current_year - pub_year, 0)
    return math.exp(-TIME_DECAY * delta)


def _journal_score(journal: str, metrics: dict, max_log_if: float) -> float:
    if not metrics:
        return 0.5
    if_val = metrics.get(journal.lower())
    if if_val is None or if_val <= 0:
        return 0.0
    return math.log(if_val + 1) / max_log_if


def rerank(articles: list[dict], keywords: str, metrics: dict | None = None) -> list[dict]:
    if not articles:
        return []

    if metrics is None:
        metrics = {}

    query_tokens = _tokenize(keywords)
    total = len(articles)
    max_if = max(metrics.values()) if metrics else 1.0
    max_log_if = math.log(max_if + 1) if max_if > 0 else 1.0

    for i, article in enumerate(articles):
        pos = _position_score(article.get("pubmed_rank", i), total)
        kw = _keyword_score(query_tokens, article.get("title", ""), article.get("abstract", ""))
        ms = _mesh_score(query_tokens, article.get("mesh_terms", []))
        tm = _time_score(article.get("year"))
        js = _journal_score(article.get("journal", ""), metrics, max_log_if)

        score = W_POSITION * pos + W_KEYWORD * kw + W_MESH * ms + W_TIME * tm + W_JOURNAL * js
        article["_score"] = round(score, 4)
        article["_pos_score"] = round(pos, 4)
        article["_kw_score"] = round(kw, 4)
        article["_mesh_score"] = round(ms, 4)
        article["_time_score"] = round(tm, 4)
        article["_journal_score"] = round(js, 4)

    articles.sort(key=lambda a: a.get("_score", 0), reverse=True)
    return articles
