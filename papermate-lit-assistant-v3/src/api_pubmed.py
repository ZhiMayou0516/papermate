from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from src.utils import clean_text, display_value, safe_int

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return clean_text("".join(node.itertext()))


def _first_text(root: ET.Element, path: str) -> str:
    return _text(root.find(path))


def _parse_pub_date(article: ET.Element) -> tuple[str, int | None]:
    article_date = article.find(".//ArticleDate")
    if article_date is not None:
        year = _first_text(article_date, "Year")
        month = _first_text(article_date, "Month")
        day = _first_text(article_date, "Day")
        date = "-".join([p.zfill(2) if len(p) == 1 else p for p in [year, month, day] if p])
        return display_value(date), safe_int(year)

    pub_date = article.find(".//Journal/JournalIssue/PubDate")
    if pub_date is not None:
        year = _first_text(pub_date, "Year")
        medline_date = _first_text(pub_date, "MedlineDate")
        if not year and medline_date[:4].isdigit():
            year = medline_date[:4]
        month = _first_text(pub_date, "Month")
        day = _first_text(pub_date, "Day")
        date = " ".join([p for p in [year, month, day] if p]) or medline_date
        return display_value(date), safe_int(year)

    return "N/A", None


def _parse_abstract(article: ET.Element) -> str:
    parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        label = node.attrib.get("Label") or node.attrib.get("NlmCategory")
        text = _text(node)
        if text:
            parts.append(f"{label}: {text}" if label else text)
    return display_value(" ".join(parts))


def _parse_authors(article: ET.Element) -> str:
    names = []
    for author in article.findall(".//AuthorList/Author"):
        collective = _first_text(author, "CollectiveName")
        if collective:
            names.append(collective)
            continue
        last = _first_text(author, "LastName")
        fore = _first_text(author, "ForeName") or _first_text(author, "Initials")
        name = clean_text(f"{fore} {last}")
        if name:
            names.append(name)
    return ", ".join(names) if names else "N/A"


def _parse_affiliations(article: ET.Element) -> str:
    affiliations = []
    for node in article.findall(".//AffiliationInfo/Affiliation"):
        aff = _text(node)
        if aff and aff not in affiliations:
            affiliations.append(aff)
    return "; ".join(affiliations[:8]) if affiliations else "N/A"


def _parse_doi(pubmed_article: ET.Element) -> str:
    for node in pubmed_article.findall(".//ArticleIdList/ArticleId"):
        if node.attrib.get("IdType", "").lower() == "doi":
            return display_value(_text(node))
    for node in pubmed_article.findall(".//ELocationID"):
        if node.attrib.get("EIdType", "").lower() == "doi":
            return display_value(_text(node))
    return "N/A"


def _search_pubmed_ids(query: str, limit: int, timeout: int) -> tuple[list[str], str | None]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max(1, min(int(limit), 100)),
        "sort": "relevance",
    }
    headers = {"User-Agent": "papermate-lit-assistant/0.2"}

    try:
        response = requests.get(ESEARCH_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout:
        return [], "PubMed request timed out."
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return [], f"PubMed HTTP error: {status}."
    except requests.RequestException as exc:
        return [], f"PubMed request failed: {exc}"
    except ValueError:
        return [], "PubMed returned invalid JSON."

    ids = payload.get("esearchresult", {}).get("idlist", [])
    return ids, None


def search_pubmed(query: str, limit: int = 10, timeout: int = 15) -> tuple[list[dict], str | None]:
    query = clean_text(query)
    if not query:
        return [], "PubMed: empty query."

    ids, error = _search_pubmed_ids(query, limit, timeout)
    if error:
        return [], error
    if not ids:
        return [], None

    params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
    }
    headers = {"User-Agent": "papermate-lit-assistant/0.2"}

    try:
        response = requests.get(EFETCH_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.Timeout:
        return [], "PubMed detail request timed out."
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return [], f"PubMed detail HTTP error: {status}."
    except requests.RequestException as exc:
        return [], f"PubMed detail request failed: {exc}"

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return [], "PubMed returned invalid XML."

    papers = []
    for pubmed_article in root.findall(".//PubmedArticle"):
        article = pubmed_article.find(".//Article")
        if article is None:
            continue

        pmid = _first_text(pubmed_article, ".//PMID")
        title = _first_text(article, "ArticleTitle")
        journal = _first_text(article, ".//Journal/Title") or _first_text(article, ".//Journal/ISOAbbreviation")
        publication_date, year = _parse_pub_date(article)
        doi = _parse_doi(pubmed_article)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "N/A"

        papers.append(
            {
                "source": "PubMed",
                "paper_id": display_value(pmid),
                "title": display_value(title),
                "authors": _parse_authors(article),
                "year": year,
                "publication_date": publication_date,
                "venue": display_value(journal),
                "journal": display_value(journal),
                "abstract": _parse_abstract(article),
                "doi": doi,
                "url": display_value(url),
                "citation_count": None,
                "field": "Biomedical literature",
                "impact_factor": "N/A",
                "affiliations": _parse_affiliations(article),
            }
        )

    return papers, None
