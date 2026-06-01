from __future__ import annotations

import requests

from src.utils import clean_text, display_value, safe_int

EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _pick_url(item: dict) -> str:
    urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
    for url_info in urls:
        url = clean_text(url_info.get("url"))
        if url:
            return url
    doi = clean_text(item.get("doi"))
    if doi:
        return f"https://doi.org/{doi}"
    pmcid = clean_text(item.get("pmcid"))
    if pmcid:
        return f"https://europepmc.org/article/PMC/{pmcid}"
    return display_value(item.get("url"))


def search_biorxiv(query: str, limit: int = 10, timeout: int = 15) -> tuple[list[dict], str | None]:
    query = clean_text(query)
    if not query:
        return [], "bioRxiv: empty query."

    europepmc_query = f'({query}) AND SRC:PPR AND PUBLISHER:"bioRxiv"'
    params = {
        "query": europepmc_query,
        "format": "json",
        "pageSize": max(1, min(int(limit), 100)),
        "sort": "RELEVANCE",
    }
    headers = {"User-Agent": "papermate-lit-assistant/0.2"}

    try:
        response = requests.get(EUROPE_PMC_SEARCH_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout:
        return [], "bioRxiv/Europe PMC request timed out."
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return [], f"bioRxiv/Europe PMC HTTP error: {status}."
    except requests.RequestException as exc:
        return [], f"bioRxiv/Europe PMC request failed: {exc}"

    try:
        payload = response.json()
    except ValueError:
        return [], "bioRxiv/Europe PMC returned invalid JSON."

    items = payload.get("resultList", {}).get("result", [])
    if not items:
        return [], None

    papers = []
    for item in items:
        date = display_value(item.get("firstPublicationDate") or item.get("firstIndexDate"))
        year = safe_int(date[:4]) if date != "N/A" and len(date) >= 4 else None
        journal = display_value(item.get("journalTitle") or "bioRxiv preprint")
        papers.append(
            {
                "source": "bioRxiv via Europe PMC",
                "paper_id": display_value(item.get("id")),
                "title": display_value(item.get("title")),
                "authors": display_value(item.get("authorString")),
                "year": year,
                "publication_date": date,
                "venue": journal,
                "journal": journal,
                "abstract": display_value(item.get("abstractText")),
                "doi": display_value(item.get("doi")),
                "url": _pick_url(item),
                "citation_count": safe_int(item.get("citedByCount")),
                "field": "Life science preprint",
                "impact_factor": "N/A",
                "affiliations": display_value(item.get("affiliation")),
            }
        )

    return papers, None
