from __future__ import annotations

import requests

from src.utils import clean_text, display_value, safe_int

SEMANTIC_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

SEMANTIC_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "authors.name",
        "authors.affiliations",
        "year",
        "venue",
        "abstract",
        "externalIds",
        "url",
        "citationCount",
        "journal",
        "publicationVenue",
        "publicationDate",
        "fieldsOfStudy",
    ]
)


def _parse_authors(authors: list[dict] | None) -> str:
    if not authors:
        return "N/A"
    names = [clean_text(author.get("name")) for author in authors if author.get("name")]
    return ", ".join(names) if names else "N/A"


def _parse_affiliations(authors: list[dict] | None) -> str:
    if not authors:
        return "N/A"
    affiliations = []
    for author in authors:
        for aff in author.get("affiliations") or []:
            aff_text = clean_text(aff)
            if aff_text and aff_text not in affiliations:
                affiliations.append(aff_text)
    return "; ".join(affiliations[:8]) if affiliations else "N/A"


def _parse_venue(item: dict) -> str:
    venue = clean_text(item.get("venue"))
    if venue:
        return venue

    journal = item.get("journal") or {}
    journal_name = clean_text(journal.get("name"))
    if journal_name:
        return journal_name

    publication_venue = item.get("publicationVenue") or {}
    publication_venue_name = clean_text(publication_venue.get("name"))
    if publication_venue_name:
        return publication_venue_name

    return "N/A"


def _parse_field(item: dict) -> str:
    fields = item.get("fieldsOfStudy") or []
    fields = [clean_text(f) for f in fields if clean_text(f)]
    return ", ".join(fields) if fields else "N/A"


def search_semantic_scholar(query: str, limit: int = 10, timeout: int = 15) -> tuple[list[dict], str | None]:
    query = clean_text(query)
    if not query:
        return [], "Semantic Scholar: empty query."

    params = {
        "query": query,
        "limit": max(1, min(int(limit), 100)),
        "offset": 0,
        "fields": SEMANTIC_FIELDS,
    }
    headers = {"User-Agent": "papermate-lit-assistant/0.2"}

    try:
        response = requests.get(SEMANTIC_SEARCH_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout:
        return [], "Semantic Scholar request timed out."
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        if status == 429:
            return [], "Semantic Scholar rate limit reached. Please retry later."
        return [], f"Semantic Scholar HTTP error: {status}."
    except requests.RequestException as exc:
        return [], f"Semantic Scholar request failed: {exc}"

    try:
        payload = response.json()
    except ValueError:
        return [], "Semantic Scholar returned invalid JSON."

    raw_papers = payload.get("data", [])
    if not raw_papers:
        return [], None

    papers = []
    for item in raw_papers:
        external_ids = item.get("externalIds") or {}
        doi = external_ids.get("DOI") or external_ids.get("doi")
        venue = _parse_venue(item)
        paper = {
            "source": "Semantic Scholar",
            "paper_id": display_value(item.get("paperId")),
            "title": display_value(item.get("title")),
            "authors": _parse_authors(item.get("authors")),
            "year": safe_int(item.get("year")),
            "publication_date": display_value(item.get("publicationDate")),
            "venue": venue,
            "journal": venue,
            "abstract": display_value(item.get("abstract")),
            "doi": display_value(doi),
            "url": display_value(item.get("url")),
            "citation_count": safe_int(item.get("citationCount")),
            "field": _parse_field(item),
            "impact_factor": "N/A",
            "affiliations": _parse_affiliations(item.get("authors")),
        }
        papers.append(paper)

    return papers, None
