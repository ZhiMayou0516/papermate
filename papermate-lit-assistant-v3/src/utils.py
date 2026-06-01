from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable

CATEGORIES = [
    "Medical AI",
    "Rehabilitation Engineering",
    "Bio-signal",
    "Geology",
    "Other",
]

PROJECTS = [
    "General Reading",
    "Medical Image Segmentation",
    "Lower-limb Exoskeleton",
    "LAMP Curve AI",
    "ECG / Bio-signal",
    "Igneous Petrology",
    "Summer Camp Portfolio",
]

STATUSES = ["待读", "已读", "收藏"]

NOTE_TYPES = ["General", "Method", "Dataset", "Result", "Limitation", "Idea", "Question"]

PAPER_TYPES = ["Review", "Method", "Dataset", "Application", "Clinical", "Geology", "Theory", "Other"]

PRIORITIES = ["High", "Medium", "Low"]

VOCAB_DIFFICULTIES = ["Easy", "Medium", "Hard"]

NA_VALUES = {"", "none", "null", "nan", "n/a", "na"}

CATEGORY_KEYWORDS = {
    "Medical AI": [
        "medical image", "segmentation", "diagnosis", "clinical", "radiology", "mri", "ct", "ultrasound",
        "deep learning", "machine learning", "transformer", "cnn", "medicine", "healthcare", "computer-aided",
        "biomedical", "surgical", "pathology", "classification", "detection",
    ],
    "Rehabilitation Engineering": [
        "rehabilitation", "exoskeleton", "prosthesis", "orthosis", "gait", "stroke", "hemiplegia",
        "assistive", "wearable robot", "lower limb", "upper limb", "therapy", "musculoskeletal", "locomotion",
        "myosuite", "mujoco", "control strategy",
    ],
    "Bio-signal": [
        "emg", "eeg", "ecg", "biopotential", "biosignal", "bio-signal", "myoelectric",
        "electromyography", "electroencephalography", "electrocardiogram", "imu", "signal processing",
        "time series", "wearable sensor", "fatigue",
    ],
    "Geology": [
        "geology", "zircon", "u-pb", "upb", "granite", "gneiss", "geochemistry", "isotope", "rodinia",
        "tectonic", "magmatism", "petrology", "igneous", "neoproterozoic", "craton", "whole-rock",
        "sr-nd", "hf isotope", "metamorphism", "arc", "rift",
    ],
}

TAG_KEYWORDS = {
    "deep-learning": ["deep learning", "neural network", "cnn", "transformer", "attention", "vit", "foundation model"],
    "segmentation": ["segmentation", "semantic segmentation", "image segmentation", "medical segmentation"],
    "exoskeleton": ["exoskeleton", "wearable robot", "assistive robot", "orthosis"],
    "stroke-rehab": ["stroke", "hemiplegia", "post-stroke", "rehabilitation"],
    "bio-signal": ["emg", "eeg", "ecg", "biosignal", "electromyography", "imu"],
    "geochemistry": ["geochemistry", "trace element", "isotope", "sr-nd", "zircon", "u-pb"],
    "review": ["review", "survey", "systematic review", "meta-analysis"],
    "dataset": ["dataset", "benchmark", "database", "cohort", "public dataset"],
    "preprint": ["preprint", "arxiv", "biorxiv", "medrxiv"],
    "clinical": ["clinical", "patient", "patients", "trial", "cohort", "diagnosis"],
    "control": ["control", "controller", "reinforcement learning", "model predictive"],
    "method": ["method", "framework", "pipeline", "algorithm", "model"],
}

TYPE_KEYWORDS = {
    "Review": ["review", "survey", "systematic review", "meta-analysis", "overview"],
    "Method": ["method", "framework", "algorithm", "model", "network", "approach", "pipeline", "architecture"],
    "Dataset": ["dataset", "benchmark", "database", "cohort", "public data", "repository"],
    "Application": ["application", "applied", "system", "prototype", "implementation", "platform"],
    "Clinical": ["clinical", "patient", "patients", "trial", "diagnosis", "therapy", "treatment"],
    "Geology": ["zircon", "u-pb", "granite", "geochemistry", "petrology", "tectonic", "magmatism"],
    "Theory": ["theory", "theoretical", "mathematical", "mechanism", "modeling"],
}

PROJECT_KEYWORDS = {
    "Medical Image Segmentation": ["segmentation", "medical image", "mri", "ct", "ultrasound", "transformer", "unet"],
    "Lower-limb Exoskeleton": ["exoskeleton", "lower limb", "gait", "rehabilitation", "stroke", "assistive", "musculoskeletal"],
    "LAMP Curve AI": ["lamp", "amplification", "fluorescence", "diagnosis", "curve", "point-of-care"],
    "ECG / Bio-signal": ["ecg", "emg", "eeg", "biosignal", "electromyography", "signal processing", "wearable sensor"],
    "Igneous Petrology": ["zircon", "u-pb", "granite", "geochemistry", "igneous", "petrology", "rodinia", "neoproterozoic"],
}

STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "are", "was", "were", "using", "based", "into", "their",
    "have", "has", "had", "our", "can", "may", "been", "will", "than", "between", "among", "study", "paper",
    "research", "method", "methods", "results", "analysis", "data", "model", "models", "approach", "system",
}

ACADEMIC_WORDS = {
    "ablation", "benchmark", "cohort", "heterogeneity", "robust", "generalization", "annotation", "segmentation",
    "diagnosis", "prognosis", "longitudinal", "retrospective", "prospective", "modality", "kinematics", "synergy",
    "locomotion", "myoelectric", "impairment", "hemiplegia", "musculoskeletal", "geochemistry", "zircon",
    "isotope", "tectonic", "magmatism", "petrogenesis", "neoproterozoic", "granitoid", "metamorphism",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def display_value(value: object, default: str = "N/A") -> str:
    text = clean_text(value)
    if text.lower() in NA_VALUES:
        return default
    return text


def safe_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_doi(doi: object) -> str:
    text = clean_text(doi).lower()
    text = text.replace("https://doi.org/", "").replace("http://doi.org/", "")
    text = text.replace("doi:", "").strip()
    return "" if text.lower() in NA_VALUES else text


def normalize_title(title: object) -> str:
    text = clean_text(title).lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_paper_id(paper_id: object) -> str:
    text = clean_text(paper_id)
    return "" if text.lower() in NA_VALUES else text


def make_unique_key(paper: dict) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"

    source = clean_text(paper.get("source")).lower()
    paper_id = normalize_paper_id(paper.get("paper_id"))
    if paper_id:
        return f"paper:{source}:{paper_id}"

    title = normalize_title(paper.get("title"))
    if title:
        title_hash = hashlib.sha1(title.encode("utf-8")).hexdigest()
        return f"title:{title_hash}"

    fallback = hashlib.sha1(str(paper).encode("utf-8")).hexdigest()
    return f"fallback:{fallback}"


def make_widget_key(paper: dict, prefix: str = "paper") -> str:
    raw = f"{prefix}:{make_unique_key(paper)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def deduplicate_papers(papers: Iterable[dict]) -> list[dict]:
    seen = set()
    unique = []
    for paper in papers:
        key = make_unique_key(paper)
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def _score_keywords(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword.lower() in text)


def infer_category_and_tags(paper: dict) -> tuple[str, str, str]:
    text = " ".join(
        [
            clean_text(paper.get("title")),
            clean_text(paper.get("abstract")),
            clean_text(paper.get("venue")),
            clean_text(paper.get("journal")),
            clean_text(paper.get("field")),
        ]
    ).lower()

    best_category = "Other"
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = _score_keywords(text, keywords)
        if score > best_score:
            best_category = category
            best_score = score

    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            tags.append(tag)

    source = clean_text(paper.get("source")).lower()
    if "arxiv" in source and "preprint" not in tags:
        tags.append("preprint")
    if "biorxiv" in source and "preprint" not in tags:
        tags.append("preprint")

    field = best_category if best_category != "Other" else display_value(paper.get("field"))
    auto_tags = ", ".join(tags) if tags else "N/A"
    return best_category, field, auto_tags


def infer_project(paper: dict) -> str:
    text = " ".join([clean_text(paper.get("title")), clean_text(paper.get("abstract")), clean_text(paper.get("auto_tags"))]).lower()
    best_project = "General Reading"
    best_score = 0
    for project, keywords in PROJECT_KEYWORDS.items():
        score = _score_keywords(text, keywords)
        if score > best_score:
            best_project = project
            best_score = score
    return best_project


def extract_keywords(text: str, max_keywords: int = 8) -> str:
    text = clean_text(text).lower()
    tokens = re.findall(r"[a-z][a-z\-]{3,}", text)
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    if not tokens:
        return "N/A"
    counter = Counter(tokens)
    return ", ".join([word for word, _ in counter.most_common(max_keywords)])


def infer_paper_type_priority(paper: dict) -> tuple[str, str, int, str, str, str]:
    title = clean_text(paper.get("title"))
    abstract = clean_text(paper.get("abstract"))
    text = f"{title} {abstract} {clean_text(paper.get('journal'))} {clean_text(paper.get('auto_tags'))}".lower()

    best_type = "Other"
    best_type_score = 0
    for paper_type, keywords in TYPE_KEYWORDS.items():
        score = _score_keywords(text, keywords)
        if score > best_type_score:
            best_type = paper_type
            best_type_score = score

    category, _, tags = infer_category_and_tags(paper)
    citation_count = safe_int(paper.get("citation_count")) or 0
    year = safe_int(paper.get("year")) or 0

    relevance = 0
    relevance += 18 if category != "Other" else 4
    relevance += min(best_type_score * 10, 25)
    relevance += min(citation_count // 25, 18)
    relevance += 12 if year >= 2021 else 6 if year >= 2016 else 2
    relevance += 10 if "review" in tags.lower() or best_type == "Review" else 0
    relevance = max(0, min(relevance, 100))

    if relevance >= 60:
        priority = "High"
    elif relevance >= 35:
        priority = "Medium"
    else:
        priority = "Low"

    reasons = []
    if category != "Other":
        reasons.append(f"matches {category}")
    if best_type != "Other":
        reasons.append(f"looks like a {best_type.lower()} paper")
    if citation_count:
        reasons.append(f"{citation_count} citations")
    if year:
        reasons.append(f"published around {year}")
    if not reasons:
        reasons.append("limited metadata; needs manual check")

    keywords = extract_keywords(f"{title} {abstract}")
    reading_time = "Quick skim" if best_type in {"Review", "Dataset"} else "Normal read" if relevance >= 35 else "Scan only"
    return best_type, priority, relevance, "; ".join(reasons), keywords, reading_time


def normalize_paper_record(paper: dict) -> dict:
    inferred_category, inferred_field, inferred_tags = infer_category_and_tags(paper)
    paper_for_project = dict(paper)
    paper_for_project["auto_tags"] = paper.get("auto_tags") or inferred_tags
    paper_type, priority, triage_score, triage_reason, keywords, reading_time = infer_paper_type_priority(paper_for_project)
    journal = display_value(paper.get("journal") or paper.get("venue"))

    return {
        "source": display_value(paper.get("source")),
        "paper_id": display_value(paper.get("paper_id")),
        "title": display_value(paper.get("title")),
        "authors": display_value(paper.get("authors")),
        "year": safe_int(paper.get("year")),
        "publication_date": display_value(paper.get("publication_date")),
        "venue": display_value(paper.get("venue")),
        "journal": journal,
        "abstract": display_value(paper.get("abstract")),
        "doi": display_value(paper.get("doi")),
        "url": display_value(paper.get("url")),
        "citation_count": safe_int(paper.get("citation_count")),
        "category": display_value(paper.get("category") or inferred_category),
        "project": display_value(paper.get("project") or infer_project(paper_for_project)),
        "field": inferred_field,
        "impact_factor": display_value(paper.get("impact_factor")),
        "affiliations": display_value(paper.get("affiliations")),
        "auto_tags": display_value(paper.get("auto_tags") or inferred_tags),
        "translated_abstract": display_value(paper.get("translated_abstract")),
        "pdf_path": display_value(paper.get("pdf_path")),
        "paper_type": display_value(paper.get("paper_type") or paper_type),
        "priority": display_value(paper.get("priority") or priority),
        "triage_score": safe_int(paper.get("triage_score")) if paper.get("triage_score") else triage_score,
        "triage_reason": display_value(paper.get("triage_reason") or triage_reason),
        "keywords": display_value(paper.get("keywords") or keywords),
        "reading_time_estimate": display_value(paper.get("reading_time_estimate") or reading_time),
    }


def markdown_escape(text: object) -> str:
    cleaned = display_value(text)
    return cleaned.replace("|", "\\|")


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text or text == "N/A":
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def build_reading_card_seed(paper: dict) -> dict:
    abstract = display_value(paper.get("abstract"))
    sentences = split_sentences(abstract)
    title = display_value(paper.get("title"))
    method_terms = []
    data_terms = []
    result_terms = []

    for sentence in sentences:
        lower = sentence.lower()
        if any(k in lower for k in ["we propose", "we present", "method", "framework", "model", "algorithm", "network"]):
            method_terms.append(sentence)
        if any(k in lower for k in ["dataset", "cohort", "patients", "samples", "experiments", "database"]):
            data_terms.append(sentence)
        if any(k in lower for k in ["results", "achieved", "improved", "outperform", "demonstrate", "show"]):
            result_terms.append(sentence)

    return {
        "research_question": f"What problem does this paper address? Start from: {title}",
        "method": method_terms[0] if method_terms else "Summarize the main method, model, experimental design, or analytical workflow.",
        "data": data_terms[0] if data_terms else "Record dataset/cohort/sample source, sample size, and evaluation setting.",
        "findings": result_terms[0] if result_terms else "Write the core findings and the evidence supporting them.",
        "limitations": "Note assumptions, missing comparisons, dataset bias, small sample size, or unclear mechanism.",
        "reusable_points": "Which part can be reused in your project: background, method, dataset, metric, figure style, or discussion logic?",
        "citation_usage": "Background / Method reference / Comparison / Discussion / Future work",
        "personal_judgement": "Worth reading because... / Not central because...",
    }


def extract_vocab_candidates(text: str, max_words: int = 20) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]{4,}", clean_text(text))
    candidates = []
    seen = set()
    for token in tokens:
        t = token.lower().strip("-")
        if t in STOPWORDS or t in seen:
            continue
        if t in ACADEMIC_WORDS or len(t) >= 9 or "-" in t:
            seen.add(t)
            candidates.append(t)
        if len(candidates) >= max_words:
            break
    return candidates
