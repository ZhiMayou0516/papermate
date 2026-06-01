from __future__ import annotations

import streamlit as st

from src.utils import display_value


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.6rem; padding-bottom: 3rem; }
        h1, h2, h3 { letter-spacing: -0.02em; }
        [data-testid="stSidebar"] { background: #f8fafc; }
        .small-muted { color: #64748b; font-size: 0.92rem; }
        .empty-box {
            border: 1px dashed #cbd5e1;
            border-radius: 16px;
            padding: 1.25rem;
            background: #f8fafc;
            color: #475569;
        }
        .meta-line { color: #475569; font-size: 0.92rem; line-height: 1.65; }
        .badge {
            display: inline-block;
            padding: 0.16rem 0.55rem;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            font-size: 0.78rem;
            margin-right: 0.35rem;
            margin-top: 0.25rem;
        }
        .reader-panel {
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 1.2rem;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="empty-box">
            <strong>{title}</strong><br>
            <span>{body}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badges(value: object) -> None:
    text = display_value(value)
    if text == "N/A":
        return
    badges = [item.strip() for item in text.split(",") if item.strip()]
    if not badges:
        return
    html = "".join([f'<span class="badge">{badge}</span>' for badge in badges])
    st.markdown(html, unsafe_allow_html=True)


def render_paper_metadata(paper: dict) -> None:
    source = display_value(paper.get("source"))
    authors = display_value(paper.get("authors"))
    year = display_value(paper.get("year"))
    publication_date = display_value(paper.get("publication_date"))
    journal = display_value(paper.get("journal") or paper.get("venue"))
    doi = display_value(paper.get("doi"))
    citations = display_value(paper.get("citation_count"))
    field = display_value(paper.get("field"))
    impact_factor = display_value(paper.get("impact_factor"))

    st.markdown(
        f"""
        <div class="meta-line">
        <strong>Source:</strong> {source}
        &nbsp; · &nbsp; <strong>Year:</strong> {year}
        &nbsp; · &nbsp; <strong>Date:</strong> {publication_date}
        &nbsp; · &nbsp; <strong>Journal:</strong> {journal}
        &nbsp; · &nbsp; <strong>Citations:</strong> {citations}
        <br>
        <strong>Field:</strong> {field}
        &nbsp; · &nbsp; <strong>Impact factor:</strong> {impact_factor}
        &nbsp; · &nbsp; <strong>DOI:</strong> {doi}
        <br>
        <strong>Authors:</strong> {authors}
        </div>
        """,
        unsafe_allow_html=True,
    )
