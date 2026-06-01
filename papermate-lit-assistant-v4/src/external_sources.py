from __future__ import annotations

from urllib.parse import quote_plus


LIMITED_SOURCES = {
    "Google Scholar": {
        "reason": "Google Scholar has no official free public API. This project provides an external search link instead of scraping.",
        "url_template": "https://scholar.google.com/scholar?q={query}",
    },
    "Web of Science": {
        "reason": "Web of Science metadata access normally requires institutional subscription or Clarivate API credentials.",
        "url_template": "https://www.webofscience.com/wos/woscc/basic-search",
    },
    "CNKI": {
        "reason": "CNKI does not provide a stable free public search API for this kind of app. Use manual export/import when available.",
        "url_template": "https://kns.cnki.net/kns8s/defaultresult/index?kw={query}",
    },
}


def build_external_links(query: str) -> list[dict]:
    encoded = quote_plus(query or "")
    links = []
    for name, meta in LIMITED_SOURCES.items():
        template = meta["url_template"]
        url = template.format(query=encoded) if "{query}" in template else template
        links.append({"name": name, "url": url, "reason": meta["reason"]})
    return links
