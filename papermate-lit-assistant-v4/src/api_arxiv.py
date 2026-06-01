from __future__ import annotations

import re

import feedparser
import requests

from src.utils import clean_text, display_value, safe_int

ARXIV_QUERY_URL = "https://export.arxiv.org/api/query"


def _build_arxiv_query(query: str) -> str:
    terms = [t for t in re.split(r"\s+", clean_text(query)) if t]
    if not terms:
        return ""
    return " AND ".join([f"all:{term}" for term in terms])


def _parse_authors(entry) -> str:
    authors = []
    for author in getattr(entry, "authors", []) or []:
        name = clean_text(author.get("name") if isinstance(author, dict) else getattr(author, "name", ""))
        if name:
            authors.append(name)
    return ", ".join(authors) if authors else "N/A"


def _parse_year(entry) -> int | None:
    published = clean_text(getattr(entry, "published", ""))
    if len(published) >= 4 and published[:4].isdigit():
        return safe_int(published[:4])
    return None


def _parse_arxiv_id(entry) -> str:
    entry_id = clean_text(getattr(entry, "id", ""))
    if "/abs/" in entry_id:
        return entry_id.rsplit("/abs/", 1)[-1]
    return entry_id.rsplit("/", 1)[-1] if entry_id else "N/A"


def _parse_doi(entry) -> str:
    doi = clean_text(getattr(entry, "arxiv_doi", ""))
    return display_value(doi)


def _parse_venue(entry) -> str:
    journal_ref = clean_text(getattr(entry, "arxiv_journal_ref", ""))
    if journal_ref:
        return journal_ref
    return "arXiv preprint"


def search_arxiv(query: str, limit: int = 10, timeout: int = 15) -> tuple[list[dict], str | None]:
    query = clean_text(query)
    if not query:
        return [], "arXiv: empty query."

    search_query = _build_arxiv_query(query)
    if not search_query:
        return [], "arXiv: could not build query."

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max(1, min(int(limit), 100)),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    headers = {"User-Agent": "papermate-lit-assistant/0.2"}

    try:
        response = requests.get(ARXIV_QUERY_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout:
        return [], "arXiv request timed out."
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return [], f"arXiv HTTP error: {status}."
    except requests.RequestException as exc:
        return [], f"arXiv request failed: {exc}"

    feed = feedparser.parse(response.text)
    if getattr(feed, "bozo", False) and not feed.entries:
        return [], "arXiv returned an invalid feed."
    if not feed.entries:
        return [], None

    papers = []
    for entry in feed.entries:
        venue = _parse_venue(entry)
        paper = {
            "source": "arXiv",
            "paper_id": _parse_arxiv_id(entry),
            "title": display_value(getattr(entry, "title", "")),
            "authors": _parse_authors(entry),
            "year": _parse_year(entry),
            "publication_date": display_value(getattr(entry, "published", "")[:10]),
            "venue": venue,
            "journal": venue,
            "abstract": display_value(getattr(entry, "summary", "")),
            "doi": _parse_doi(entry),
            "url": display_value(getattr(entry, "link", "")),
            "citation_count": None,
            "field": "N/A",
            "impact_factor": "N/A",
            "affiliations": "N/A",
        }
        papers.append(paper)

    return papers, None
