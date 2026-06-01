from __future__ import annotations

import base64
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.api_arxiv import search_arxiv
from src.api_europepmc import search_biorxiv
from src.api_pubmed import search_pubmed
from src.api_semantic import search_semantic_scholar
from src.database import (
    PDF_DIR,
    add_or_update_paper,
    add_reading_note,
    add_vocabulary,
    delete_paper,
    delete_reading_note,
    delete_vocabulary,
    get_dashboard_stats,
    get_paper,
    get_reading_card,
    init_db,
    list_papers,
    list_reading_cards,
    list_reading_notes,
    list_translation_practice,
    list_vocabulary,
    review_vocabulary,
    save_translation_practice,
    update_paper,
    update_pdf_path,
    update_translated_abstract,
    update_vocabulary,
    upsert_reading_card,
)
from src.exporter import (
    literature_matrix_to_markdown,
    matrix_to_csv_bytes,
    papers_to_csv_bytes,
    papers_to_markdown,
    reading_notes_to_markdown,
    vocabulary_to_csv_bytes,
    weekly_report_to_markdown,
)
from src.external_sources import build_external_links
from src.translator import translate_text
from src.ui_components import inject_global_css, render_badges, render_empty_state, render_paper_metadata
from src.utils import (
    CATEGORIES,
    NOTE_TYPES,
    PAPER_TYPES,
    PRIORITIES,
    PROJECTS,
    STATUSES,
    VOCAB_DIFFICULTIES,
    build_reading_card_seed,
    clean_text,
    display_value,
    extract_vocab_candidates,
    infer_category_and_tags,
    infer_paper_type_priority,
    infer_project,
    make_widget_key,
    split_sentences,
)

st.set_page_config(
    page_title="PaperMate Lit Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
inject_global_css()

SEARCH_SOURCES = [
    "All open sources",
    "Semantic Scholar",
    "arXiv",
    "PubMed",
    "bioRxiv",
]


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return text[:120] or "paper"


def sidebar_navigation() -> str:
    with st.sidebar:
        st.markdown("## 📚 PaperMate")
        st.caption("Research reading workflow · notes · vocabulary training")
        page = st.radio(
            "Navigation",
            [
                "Search Papers",
                "Library",
                "Reader",
                "Research Workflow",
                "Vocabulary",
                "Training",
                "Dashboard",
                "About",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Open APIs first. Local-first SQLite. No paid key required.")
    return page


def render_translation_block(text: str, key: str, paper_id: int | None = None) -> None:
    if st.button("Translate", key=f"translate_{key}"):
        with st.spinner("Translating..."):
            translated, error = translate_text(text)
        if error:
            st.warning(error)
        else:
            st.session_state[f"translated_{key}"] = translated
            if paper_id is not None:
                update_translated_abstract(paper_id, translated)
                st.success("Translation saved to this paper.")

    translated_text = st.session_state.get(f"translated_{key}")
    if translated_text:
        st.markdown("**中文翻译**")
        st.info(translated_text)


def search_open_sources(query: str, source: str, limit: int) -> tuple[list[dict], list[str]]:
    results = []
    errors = []

    if source in ["All open sources", "Semantic Scholar"]:
        papers, error = search_semantic_scholar(query, limit=limit)
        results.extend(papers)
        if error:
            errors.append(error)

    if source in ["All open sources", "arXiv"]:
        papers, error = search_arxiv(query, limit=limit)
        results.extend(papers)
        if error:
            errors.append(error)

    if source in ["All open sources", "PubMed"]:
        papers, error = search_pubmed(query, limit=limit)
        results.extend(papers)
        if error:
            errors.append(error)

    if source in ["All open sources", "bioRxiv"]:
        papers, error = search_biorxiv(query, limit=limit)
        results.extend(papers)
        if error:
            errors.append(error)

    from src.utils import deduplicate_papers

    return deduplicate_papers(results)[:limit], errors


def render_external_links(query: str) -> None:
    st.markdown("#### External sources")
    st.caption("These sources are useful, but not connected by default because they do not provide stable free public APIs for this project.")
    for item in build_external_links(query):
        with st.container(border=True):
            st.markdown(f"**{item['name']}**")
            st.caption(item["reason"])
            st.link_button(f"Open {item['name']}", item["url"])


def render_triage_panel(paper: dict) -> tuple[str, str, int, str, str, str]:
    paper_type, priority, score, reason, keywords, reading_time = infer_paper_type_priority(paper)
    cols = st.columns([1, 1, 1, 2])
    cols[0].metric("Type", paper_type)
    cols[1].metric("Priority", priority)
    cols[2].metric("Score", score)
    cols[3].markdown(f"**Why:** {reason}")
    st.caption(f"Keywords: {keywords} · Suggested reading mode: {reading_time}")
    return paper_type, priority, score, reason, keywords, reading_time


def render_search_result_card(paper: dict, index: int) -> None:
    key = make_widget_key(paper, prefix=f"search_{index}")
    category_guess, field_guess, tags_guess = infer_category_and_tags(paper)
    project_guess = infer_project({**paper, "auto_tags": tags_guess})
    paper_type, priority, score, reason, keywords, reading_time = infer_paper_type_priority({**paper, "auto_tags": tags_guess})

    with st.container(border=True):
        title = display_value(paper.get("title"))
        url = display_value(paper.get("url"))
        if url != "N/A":
            st.markdown(f"### [{title}]({url})")
        else:
            st.markdown(f"### {title}")

        paper["field"] = paper.get("field") or field_guess
        paper["auto_tags"] = paper.get("auto_tags") or tags_guess
        render_paper_metadata(paper)
        render_badges(tags_guess)

        st.markdown("#### Paper triage")
        render_triage_panel({**paper, "auto_tags": tags_guess})

        with st.expander("Abstract", expanded=False):
            st.write(display_value(paper.get("abstract")))
            render_translation_block(display_value(paper.get("abstract")), key)

        with st.expander("Affiliations / institution info", expanded=False):
            st.write(display_value(paper.get("affiliations")))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            category = st.selectbox(
                "Category",
                CATEGORIES,
                index=CATEGORIES.index(category_guess) if category_guess in CATEGORIES else CATEGORIES.index("Other"),
                key=f"category_{key}",
            )
        with col2:
            project = st.selectbox(
                "Project",
                PROJECTS,
                index=PROJECTS.index(project_guess) if project_guess in PROJECTS else 0,
                key=f"project_{key}",
            )
        with col3:
            status = st.selectbox("Status", STATUSES, index=STATUSES.index("待读"), key=f"status_{key}")
        with col4:
            impact_factor = st.text_input(
                "Impact factor",
                value=display_value(paper.get("impact_factor")),
                help="JCR/WoS impact factor is licensed data, so this field is editable rather than scraped.",
                key=f"if_{key}",
            )

        notes = st.text_area(
            "Personal notes",
            value="",
            height=90,
            placeholder="Why is this paper useful? Methods, datasets, limitations, or possible citation use...",
            key=f"notes_{key}",
        )

        paper_to_save = dict(paper)
        paper_to_save.update(
            {
                "impact_factor": impact_factor,
                "category": category,
                "project": project,
                "field": field_guess,
                "auto_tags": tags_guess,
                "paper_type": paper_type,
                "priority": priority,
                "triage_score": score,
                "triage_reason": reason,
                "keywords": keywords,
                "reading_time_estimate": reading_time,
            }
        )

        if st.button("Save to library", key=f"save_{key}", type="primary"):
            paper_id, created = add_or_update_paper(paper_to_save, category=category, status=status, notes=notes, project=project)
            if created:
                st.success(f"Saved to library. Local ID: {paper_id}")
            else:
                st.info(f"Already exists. Updated local record ID: {paper_id}")


def run_search_page() -> None:
    st.markdown("# Search Papers")
    st.caption("Search open literature sources, triage papers, and save useful records into a project-based library.")

    with st.form("search_form"):
        col1, col2, col3 = st.columns([3, 1.7, 1.2])
        with col1:
            query = st.text_input("Keyword", placeholder="medical image segmentation, lower limb exoskeleton, zircon U-Pb...")
        with col2:
            source = st.selectbox("Data source", SEARCH_SOURCES)
        with col3:
            limit = st.slider("Return count", min_value=5, max_value=80, value=20, step=5)
        submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

    if submitted:
        if not query.strip():
            st.warning("Please enter a keyword first.")
            return
        with st.spinner("Searching open sources..."):
            results, errors = search_open_sources(query, source, limit)
        st.session_state["search_query"] = query
        st.session_state["search_results"] = results
        st.session_state["search_errors"] = errors

    query_for_links = st.session_state.get("search_query", "")
    if query_for_links:
        with st.expander("Google Scholar / Web of Science / CNKI shortcuts", expanded=False):
            render_external_links(query_for_links)

    for error in st.session_state.get("search_errors", []):
        st.warning(error)

    results = st.session_state.get("search_results", [])
    if not results:
        render_empty_state("No search results yet.", "Try keywords from your research areas, then save useful papers into the library.")
        return

    st.markdown(f"#### Results: {len(results)}")
    for idx, paper in enumerate(results):
        render_search_result_card(paper, idx)


def build_library_filters():
    col1, col2, col3, col4, col5, col6 = st.columns([2.2, 1.2, 1.2, 1.4, 1.1, 1.3])
    with col1:
        keyword = st.text_input("Search local library", placeholder="title, author, abstract, DOI, notes, institution...")
    with col2:
        category_filter = st.selectbox("Category", ["All"] + CATEGORIES)
    with col3:
        status_filter = st.selectbox("Status", ["All"] + STATUSES)
    with col4:
        project_filter = st.selectbox("Project", ["All"] + PROJECTS)
    with col5:
        priority_filter = st.selectbox("Priority", ["All"] + PRIORITIES)
    with col6:
        sort_label = st.selectbox(
            "Sort by",
            ["Newest saved", "Recently updated", "Triage score", "Year desc", "Year asc", "Citation desc", "Journal A-Z", "Title A-Z"],
        )

    sort_map = {
        "Newest saved": "created_at DESC",
        "Recently updated": "updated_at DESC",
        "Triage score": "triage_score DESC",
        "Year desc": "year DESC",
        "Year asc": "year ASC",
        "Citation desc": "citation_count DESC",
        "Journal A-Z": "journal ASC",
        "Title A-Z": "title ASC",
    }
    return keyword, category_filter, status_filter, project_filter, priority_filter, sort_map[sort_label]


def run_library_page() -> None:
    st.markdown("# Library")
    st.caption("Manage saved papers, project labels, triage fields, metadata, and exports.")

    keyword, category_filter, status_filter, project_filter, priority_filter, order_by = build_library_filters()
    papers = list_papers(
        keyword=keyword,
        category=None if category_filter == "All" else category_filter,
        status=None if status_filter == "All" else status_filter,
        project=None if project_filter == "All" else project_filter,
        priority=None if priority_filter == "All" else priority_filter,
        order_by=order_by,
    )

    st.markdown(f"#### Saved papers: {len(papers)}")
    if not papers:
        render_empty_state("No saved papers found.", "Search papers first, then save useful records to the library.")
        return

    df = pd.DataFrame(papers)
    visible_cols = [
        "id", "title", "year", "journal", "project", "paper_type", "priority", "triage_score", "keywords", "category", "status", "source"
    ]
    st.dataframe(df[[c for c in visible_cols if c in df.columns]], use_container_width=True, hide_index=True)

    export_col1, export_col2 = st.columns(2)
    with export_col1:
        st.download_button("Export CSV", data=papers_to_csv_bytes(papers), file_name="papermate_library.csv", mime="text/csv", use_container_width=True)
    with export_col2:
        st.download_button("Export Markdown", data=papers_to_markdown(papers), file_name="papermate_library.md", mime="text/markdown", use_container_width=True)

    st.divider()
    st.markdown("### Edit records")

    for paper in papers:
        with st.expander(f"#{paper['id']} · {paper['title']}", expanded=False):
            render_paper_metadata(paper)
            render_badges(paper.get("auto_tags"))
            st.markdown("**Triage**")
            st.info(f"{display_value(paper.get('paper_type'))} · {display_value(paper.get('priority'))} · Score {display_value(paper.get('triage_score'))} · {display_value(paper.get('triage_reason'))}")
            st.caption(f"Keywords: {display_value(paper.get('keywords'))}")
            st.markdown("**Abstract**")
            st.write(display_value(paper.get("abstract")))

            with st.form(f"edit_form_{paper['id']}"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    category = st.selectbox(
                        "Category", CATEGORIES,
                        index=CATEGORIES.index(paper.get("category") or "Other") if (paper.get("category") or "Other") in CATEGORIES else CATEGORIES.index("Other"),
                        key=f"edit_category_{paper['id']}",
                    )
                with col2:
                    project = st.selectbox(
                        "Project", PROJECTS,
                        index=PROJECTS.index(paper.get("project") or "General Reading") if (paper.get("project") or "General Reading") in PROJECTS else 0,
                        key=f"edit_project_{paper['id']}",
                    )
                with col3:
                    status = st.selectbox(
                        "Status", STATUSES,
                        index=STATUSES.index(paper.get("status") or "待读") if (paper.get("status") or "待读") in STATUSES else STATUSES.index("待读"),
                        key=f"edit_status_{paper['id']}",
                    )
                with col4:
                    priority = st.selectbox(
                        "Priority", PRIORITIES,
                        index=PRIORITIES.index(paper.get("priority") or "Medium") if (paper.get("priority") or "Medium") in PRIORITIES else 1,
                        key=f"edit_priority_{paper['id']}",
                    )

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    paper_type = st.selectbox(
                        "Paper type", PAPER_TYPES,
                        index=PAPER_TYPES.index(paper.get("paper_type") or "Other") if (paper.get("paper_type") or "Other") in PAPER_TYPES else PAPER_TYPES.index("Other"),
                        key=f"edit_type_{paper['id']}",
                    )
                with col_b:
                    triage_score = st.number_input("Triage score", min_value=0, max_value=100, value=int(paper.get("triage_score") or 0), key=f"edit_score_{paper['id']}")
                with col_c:
                    impact_factor = st.text_input("Impact factor", value=display_value(paper.get("impact_factor")), key=f"edit_if_{paper['id']}")

                field = st.text_input("Field", value=display_value(paper.get("field")), key=f"edit_field_{paper['id']}")
                auto_tags = st.text_input("Tags", value=display_value(paper.get("auto_tags")), key=f"edit_tags_{paper['id']}")
                keywords = st.text_input("Keywords", value=display_value(paper.get("keywords")), key=f"edit_keywords_{paper['id']}")
                triage_reason = st.text_area("Triage reason", value=display_value(paper.get("triage_reason")), height=80, key=f"edit_reason_{paper['id']}")
                affiliations = st.text_area("Affiliations / institutions", value=display_value(paper.get("affiliations")), height=90, key=f"edit_aff_{paper['id']}")
                notes = st.text_area("Personal notes", value=paper.get("notes") or "", height=100, key=f"edit_notes_{paper['id']}")

                submitted = st.form_submit_button("Update record", type="primary")
                if submitted:
                    update_paper(
                        paper_id=paper["id"], category=category, project=project, status=status, notes=notes,
                        field=field, impact_factor=impact_factor, affiliations=affiliations, auto_tags=auto_tags,
                        translated_abstract=paper.get("translated_abstract") or "", pdf_path=paper.get("pdf_path") or "",
                        paper_type=paper_type, priority=priority, triage_score=int(triage_score), triage_reason=triage_reason,
                        keywords=keywords, reading_time_estimate=paper.get("reading_time_estimate") or "",
                    )
                    st.success("Record updated.")
                    st.rerun()

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Open in Reader", key=f"open_reader_{paper['id']}"):
                    st.session_state["reader_paper_id"] = paper["id"]
                    st.success("Selected for Reader. Open the Reader page from the sidebar.")
            with col_b:
                if st.button("Delete record", key=f"delete_{paper['id']}"):
                    delete_paper(paper["id"])
                    st.warning("Record deleted.")
                    st.rerun()


def render_pdf_viewer(pdf_path: str) -> None:
    path = Path(pdf_path)
    if not path.exists():
        st.warning("The linked PDF file was not found locally.")
        return
    try:
        with open(path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="760" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except OSError as exc:
        st.warning(f"Could not open PDF: {exc}")


def render_reading_card_editor(paper: dict) -> None:
    paper_id = int(paper["id"])
    existing = get_reading_card(paper_id)
    seed = build_reading_card_seed(paper)
    values = {key: (existing.get(key) if existing else seed.get(key, "")) for key in seed}
    rating_default = int(existing.get("rating") if existing else 3)

    st.markdown("### Structured reading card")
    st.caption("This is the core difference from Zotero: turn a paper into reusable research material.")

    if st.button("Regenerate template from abstract", key=f"regen_card_{paper_id}"):
        values = seed
        st.session_state[f"card_seed_{paper_id}"] = seed

    if st.session_state.get(f"card_seed_{paper_id}"):
        values = st.session_state[f"card_seed_{paper_id}"]

    with st.form(f"reading_card_{paper_id}"):
        research_question = st.text_area("Research question", value=values.get("research_question") or "", height=80)
        method = st.text_area("Method / model / workflow", value=values.get("method") or "", height=100)
        data = st.text_area("Data / samples / experiment setting", value=values.get("data") or "", height=90)
        findings = st.text_area("Key findings", value=values.get("findings") or "", height=100)
        limitations = st.text_area("Limitations", value=values.get("limitations") or "", height=90)
        reusable_points = st.text_area("Reusable points for my project", value=values.get("reusable_points") or "", height=100)
        citation_usage = st.text_input("Where can I cite this?", value=values.get("citation_usage") or "")
        personal_judgement = st.text_area("My judgement", value=values.get("personal_judgement") or "", height=90)
        rating = st.slider("Reading value", min_value=1, max_value=5, value=rating_default)

        submitted = st.form_submit_button("Save reading card", type="primary")
        if submitted:
            upsert_reading_card(
                paper_id=paper_id,
                research_question=research_question,
                method=method,
                data=data,
                findings=findings,
                limitations=limitations,
                reusable_points=reusable_points,
                citation_usage=citation_usage,
                personal_judgement=personal_judgement,
                rating=rating,
            )
            st.success("Reading card saved.")
            st.rerun()


def run_reader_page() -> None:
    st.markdown("# Reader")
    st.caption("Read abstracts or local PDFs, translate text, create reading cards, and write notes.")

    papers = list_papers(order_by="created_at DESC")
    if not papers:
        render_empty_state("No papers in library.", "Save a paper first, then come back to the Reader.")
        return

    options = {f"#{p['id']} · {p['title'][:90]}": p["id"] for p in papers}
    default_id = st.session_state.get("reader_paper_id")
    labels = list(options.keys())
    default_index = 0
    if default_id:
        for i, label in enumerate(labels):
            if options[label] == default_id:
                default_index = i
                break

    selected_label = st.selectbox("Select a paper", labels, index=default_index)
    paper_id = options[selected_label]
    st.session_state["reader_paper_id"] = paper_id
    paper = get_paper(paper_id)
    if not paper:
        st.warning("Selected paper no longer exists.")
        return

    left, right = st.columns([1.35, 1])
    with left:
        title = display_value(paper.get("title"))
        url = display_value(paper.get("url"))
        if url != "N/A":
            st.markdown(f"## [{title}]({url})")
        else:
            st.markdown(f"## {title}")
        render_paper_metadata(paper)
        render_badges(paper.get("auto_tags"))
        st.info(f"{display_value(paper.get('paper_type'))} · {display_value(paper.get('priority'))} · Score {display_value(paper.get('triage_score'))} · Project: {display_value(paper.get('project'))}")

        tab_abs, tab_pdf, tab_card = st.tabs(["Abstract reader", "Local PDF", "Reading card"])
        with tab_abs:
            st.markdown("### Abstract")
            abstract = display_value(paper.get("abstract"))
            st.write(abstract)
            if display_value(paper.get("translated_abstract")) != "N/A":
                st.markdown("### Saved translation")
                st.info(display_value(paper.get("translated_abstract")))
            render_translation_block(abstract, f"reader_{paper_id}", paper_id=paper_id)

            st.markdown("### Candidate academic words")
            candidates = extract_vocab_candidates(abstract)
            if not candidates:
                st.caption("No obvious candidates extracted.")
            else:
                selected_words = st.multiselect("Select words to add", candidates, key=f"candidate_words_{paper_id}")
                if st.button("Add selected words to vocabulary", key=f"add_candidates_{paper_id}"):
                    for word in selected_words:
                        add_vocabulary(word=word, source_title=title, context=abstract[:500], notes="Auto-extracted from abstract")
                    st.success(f"Added {len(selected_words)} words.")

        with tab_pdf:
            uploaded = st.file_uploader("Attach local PDF", type=["pdf"], key=f"pdf_upload_{paper_id}")
            if uploaded is not None:
                filename = f"{paper_id}_{safe_filename(uploaded.name)}"
                save_path = PDF_DIR / filename
                save_path.write_bytes(uploaded.getbuffer())
                update_pdf_path(paper_id, str(save_path))
                st.success("PDF attached to this paper.")
                st.rerun()

            pdf_path = display_value(paper.get("pdf_path"))
            if pdf_path != "N/A":
                st.caption(pdf_path)
                render_pdf_viewer(pdf_path)
            else:
                render_empty_state("No local PDF attached.", "Upload a PDF to use this page as a lightweight reader.")

        with tab_card:
            render_reading_card_editor(paper)

    with right:
        st.markdown("### Add free note")
        with st.form(f"note_form_{paper_id}"):
            note_type = st.selectbox("Note type", NOTE_TYPES)
            page = st.text_input("Page / section", placeholder="e.g. Abstract, Fig. 2, p. 5")
            quote = st.text_area("Quoted text", height=90, placeholder="Paste the original sentence or paragraph here.")
            note = st.text_area("Your note", height=150, placeholder="Summarize, critique, or connect this paper to your project.")
            submitted = st.form_submit_button("Save note", type="primary")
            if submitted:
                if not note.strip() and not quote.strip():
                    st.warning("Please write a note or quote first.")
                else:
                    add_reading_note(paper_id, note_type, quote, note, page)
                    st.success("Note saved.")
                    st.rerun()

        st.markdown("### Quick vocabulary")
        with st.form(f"reader_vocab_{paper_id}"):
            word = st.text_input("Word")
            meaning = st.text_input("Meaning")
            example_sentence = st.text_area("Example sentence", height=75)
            vocab_notes = st.text_area("Notes", height=75)
            difficulty = st.selectbox("Difficulty", VOCAB_DIFFICULTIES, index=1)
            vocab_submitted = st.form_submit_button("Add word")
            if vocab_submitted:
                if not word.strip():
                    st.warning("Word cannot be empty.")
                else:
                    add_vocabulary(word=word, meaning=meaning, source_title=title, example_sentence=example_sentence, context=display_value(paper.get("abstract"))[:500], notes=vocab_notes, difficulty=difficulty)
                    st.success("Word added.")

        st.markdown("### Saved notes")
        notes = list_reading_notes(paper_id)
        card = get_reading_card(paper_id)
        st.download_button(
            "Export this paper's notes as Markdown",
            data=reading_notes_to_markdown(paper, notes, card),
            file_name=f"paper_{paper_id}_reading_notes.md",
            mime="text/markdown",
            use_container_width=True,
        )
        if not notes:
            render_empty_state("No notes yet.", "Use structured notes to turn reading into reusable research material.")
        for item in notes:
            with st.container(border=True):
                st.markdown(f"**{display_value(item.get('note_type'))}** · {display_value(item.get('created_at'))}")
                if display_value(item.get("page")) != "N/A":
                    st.caption(f"Page/section: {display_value(item.get('page'))}")
                if display_value(item.get("quote")) != "N/A":
                    st.markdown(f"> {display_value(item.get('quote'))}")
                st.write(display_value(item.get("note")))
                if st.button("Delete note", key=f"delete_note_{item['id']}"):
                    delete_reading_note(item["id"])
                    st.rerun()


def run_research_workflow_page() -> None:
    st.markdown("# Research Workflow")
    st.caption("Paper triage, structured reading cards, literature matrix, and weekly reading report.")

    tab_triage, tab_matrix, tab_report = st.tabs(["Triage board", "Literature matrix", "Weekly report"])

    with tab_triage:
        st.markdown("### Paper triage board")
        col1, col2 = st.columns(2)
        with col1:
            project_filter = st.selectbox("Project", ["All"] + PROJECTS, key="triage_project")
        with col2:
            priority_filter = st.selectbox("Priority", ["All"] + PRIORITIES, key="triage_priority")
        papers = list_papers(
            project=None if project_filter == "All" else project_filter,
            priority=None if priority_filter == "All" else priority_filter,
            order_by="triage_score DESC",
        )
        if not papers:
            render_empty_state("No papers for this board.", "Save papers first, then use triage to decide what to read deeply.")
        else:
            for paper in papers:
                with st.container(border=True):
                    st.markdown(f"#### #{paper['id']} · {display_value(paper.get('title'))}")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Priority", display_value(paper.get("priority")))
                    c2.metric("Score", display_value(paper.get("triage_score")))
                    c3.metric("Type", display_value(paper.get("paper_type")))
                    c4.metric("Project", display_value(paper.get("project")))
                    st.caption(f"Reason: {display_value(paper.get('triage_reason'))}")
                    st.caption(f"Keywords: {display_value(paper.get('keywords'))}")
                    if st.button("Open in Reader", key=f"triage_open_{paper['id']}"):
                        st.session_state["reader_paper_id"] = paper["id"]
                        st.success("Selected for Reader. Open the Reader page from the sidebar.")

    with tab_matrix:
        st.markdown("### Literature matrix")
        col1, col2 = st.columns(2)
        with col1:
            project_filter = st.selectbox("Project filter", ["All"] + PROJECTS, key="matrix_project")
        with col2:
            category_filter = st.selectbox("Category filter", ["All"] + CATEGORIES, key="matrix_category")
        cards = list_reading_cards(
            project=None if project_filter == "All" else project_filter,
            category=None if category_filter == "All" else category_filter,
        )
        if not cards:
            render_empty_state("No reading cards yet.", "Open Reader and create structured reading cards first.")
        else:
            df = pd.DataFrame(cards)
            visible = ["paper_id", "title", "year", "project", "paper_type", "priority", "method", "data", "findings", "limitations", "reusable_points", "rating"]
            st.dataframe(df[[c for c in visible if c in df.columns]], use_container_width=True, hide_index=True)
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("Export matrix CSV", data=matrix_to_csv_bytes(cards), file_name="literature_matrix.csv", mime="text/csv", use_container_width=True)
            with col_b:
                st.download_button("Export matrix Markdown", data=literature_matrix_to_markdown(cards), file_name="literature_matrix.md", mime="text/markdown", use_container_width=True)

    with tab_report:
        st.markdown("### Weekly reading report")
        today = date.today()
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input("Start date", value=today - timedelta(days=7))
        with col2:
            end = st.date_input("End date", value=today)
        cards = list_reading_cards(start_date=start.isoformat(), end_date=end.isoformat())
        notes = list_reading_notes(start_date=start.isoformat(), end_date=end.isoformat())
        translations = [item for item in list_translation_practice(limit=100) if start.isoformat() <= display_value(item.get("created_at"))[:10] <= end.isoformat()]
        report = weekly_report_to_markdown(start.isoformat(), end.isoformat(), cards, notes, translations)
        st.text_area("Preview", value=report, height=420)
        st.download_button("Export weekly report Markdown", data=report, file_name="weekly_reading_report.md", mime="text/markdown", use_container_width=True)


def run_vocabulary_page() -> None:
    st.markdown("# Vocabulary")
    st.caption("Academic English notebook with source paper, context, example sentence, and spaced repetition fields.")

    with st.form("add_vocabulary_form"):
        col1, col2, col3 = st.columns([1.2, 1.4, 1])
        with col1:
            word = st.text_input("Word", placeholder="e.g. ablation")
            source_title = st.text_input("Source paper title", placeholder="Optional")
        with col2:
            meaning = st.text_input("Chinese meaning", placeholder="e.g. 消融实验；切除")
            example_sentence = st.text_area("Example sentence", placeholder="A sentence from the abstract or paper.", height=90)
        with col3:
            difficulty = st.selectbox("Difficulty", VOCAB_DIFFICULTIES, index=1)
            notes = st.text_area("Notes", placeholder="Usage, confusion points...", height=90)
        context = st.text_area("Context paragraph", placeholder="Paste the original context if useful.", height=100)
        submitted = st.form_submit_button("Add word", type="primary")
        if submitted:
            if not word.strip():
                st.warning("Word cannot be empty.")
            else:
                add_vocabulary(word=word, meaning=meaning, source_title=source_title, example_sentence=example_sentence, context=context, notes=notes, difficulty=difficulty)
                st.success("Word saved.")
                st.rerun()

    st.divider()
    col1, col2 = st.columns([2, 1])
    with col1:
        search_word = st.text_input("Search vocabulary", placeholder="word, meaning, notes, context...")
    with col2:
        due_only = st.checkbox("Due only")
    words = list_vocabulary(keyword=search_word, due_only=due_only)
    if not words:
        render_empty_state("No vocabulary records yet.", "Add words manually or extract candidate words from abstracts in Reader.")
        return

    df = pd.DataFrame(words)
    visible = ["id", "word", "meaning", "difficulty", "familiarity", "review_count", "next_review_at", "source_title", "notes"]
    st.dataframe(df[[c for c in visible if c in df.columns]], use_container_width=True, hide_index=True)
    st.download_button("Export vocabulary CSV", data=vocabulary_to_csv_bytes(words), file_name="papermate_vocabulary.csv", mime="text/csv", use_container_width=True)

    st.markdown("### Edit vocabulary")
    for item in words:
        with st.expander(f"#{item['id']} · {item['word']}", expanded=False):
            with st.form(f"vocab_edit_{item['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    word = st.text_input("Word", value=item.get("word") or "", key=f"word_{item['id']}")
                    source_title = st.text_input("Source title", value=item.get("source_title") or "", key=f"source_title_{item['id']}")
                    difficulty = st.selectbox(
                        "Difficulty", VOCAB_DIFFICULTIES,
                        index=VOCAB_DIFFICULTIES.index(item.get("difficulty") or "Medium") if (item.get("difficulty") or "Medium") in VOCAB_DIFFICULTIES else 1,
                        key=f"difficulty_{item['id']}",
                    )
                with col2:
                    meaning = st.text_input("Meaning", value=item.get("meaning") or "", key=f"meaning_{item['id']}")
                    familiarity = st.slider("Familiarity", min_value=0, max_value=5, value=int(item.get("familiarity") or 0), key=f"fam_{item['id']}")
                    notes = st.text_area("Notes", value=item.get("notes") or "", height=90, key=f"vocab_notes_{item['id']}")
                example_sentence = st.text_area("Example sentence", value=item.get("example_sentence") or "", height=75, key=f"example_{item['id']}")
                context = st.text_area("Context", value=item.get("context") or "", height=100, key=f"context_{item['id']}")
                submitted = st.form_submit_button("Update word", type="primary")
                if submitted:
                    update_vocabulary(item["id"], word=word, meaning=meaning, source_title=source_title, example_sentence=example_sentence, context=context, notes=notes, difficulty=difficulty, familiarity=familiarity)
                    st.success("Vocabulary updated.")
                    st.rerun()
            if st.button("Delete word", key=f"delete_vocab_{item['id']}"):
                delete_vocabulary(item["id"])
                st.warning("Vocabulary deleted.")
                st.rerun()


def render_vocab_training() -> None:
    st.markdown("### Spaced repetition")
    due_words = list_vocabulary(due_only=True, limit=30)
    if not due_words:
        render_empty_state("No words due today.", "Add words or come back when next_review_at arrives.")
        return

    if "training_index" not in st.session_state:
        st.session_state["training_index"] = 0
    st.session_state["training_index"] = min(st.session_state["training_index"], len(due_words) - 1)
    item = due_words[st.session_state["training_index"]]

    with st.container(border=True):
        st.caption(f"Due words: {len(due_words)} · Card {st.session_state['training_index'] + 1}/{len(due_words)}")
        st.markdown(f"# {display_value(item.get('word'))}")
        st.caption(f"Difficulty: {display_value(item.get('difficulty'))} · Familiarity: {display_value(item.get('familiarity'))}/5")
        st.markdown("**Source**")
        st.write(display_value(item.get("source_title")))

        show_answer_key = f"show_answer_{item['id']}"
        if st.button("Reveal meaning / context", key=f"reveal_{item['id']}"):
            st.session_state[show_answer_key] = True

        if st.session_state.get(show_answer_key):
            st.markdown("**Meaning**")
            st.info(display_value(item.get("meaning")))
            st.markdown("**Example sentence**")
            st.write(display_value(item.get("example_sentence")))
            st.markdown("**Context**")
            st.write(display_value(item.get("context")))
            st.markdown("**Notes**")
            st.write(display_value(item.get("notes")))

            st.markdown("#### How well did you remember it?")
            cols = st.columns(4)
            actions = [("Again", "again"), ("Hard", "hard"), ("Good", "good"), ("Easy", "easy")]
            for col, (label, grade) in zip(cols, actions):
                if col.button(label, key=f"grade_{grade}_{item['id']}", use_container_width=True):
                    review_vocabulary(item["id"], grade)
                    st.session_state.pop(show_answer_key, None)
                    st.session_state["training_index"] = min(st.session_state["training_index"], max(0, len(due_words) - 2))
                    st.rerun()

        nav1, nav2 = st.columns(2)
        if nav1.button("Previous", use_container_width=True):
            st.session_state["training_index"] = max(0, st.session_state["training_index"] - 1)
            st.rerun()
        if nav2.button("Next", use_container_width=True):
            st.session_state["training_index"] = min(len(due_words) - 1, st.session_state["training_index"] + 1)
            st.rerun()


def render_translation_training() -> None:
    st.markdown("### Abstract translation training")
    papers = [p for p in list_papers(order_by="created_at DESC") if display_value(p.get("abstract")) != "N/A"]
    if not papers:
        render_empty_state("No abstracts available.", "Save papers with abstracts first.")
        return

    options = {f"#{p['id']} · {p['title'][:90]}": p["id"] for p in papers}
    selected_label = st.selectbox("Select paper", list(options.keys()), key="translation_paper")
    paper = get_paper(options[selected_label])
    if not paper:
        return

    sentences = split_sentences(display_value(paper.get("abstract")))
    if not sentences:
        sentences = [display_value(paper.get("abstract"))]
    sentence_count = min(len(sentences), 3)
    source_text = " ".join(sentences[:sentence_count])

    st.markdown("**Original text**")
    st.info(source_text)

    with st.form("translation_practice_form"):
        user_translation = st.text_area("Your Chinese translation", height=160)
        self_score = st.slider("Self score after checking", min_value=1, max_value=5, value=3)
        notes = st.text_area("Notes / difficult terms", height=90)
        submitted = st.form_submit_button("Save practice", type="primary")
        if submitted:
            save_translation_practice(int(paper["id"]), source_text, user_translation, reference_translation="", self_score=self_score, notes=notes)
            st.success("Translation practice saved.")

    ref_key = f"translation_ref_{paper['id']}"
    if st.button("Show machine translation", key=f"show_ref_{paper['id']}"):
        with st.spinner("Translating..."):
            translated, error = translate_text(source_text)
        if error:
            st.warning(error)
        else:
            st.session_state[ref_key] = translated

    if st.session_state.get(ref_key):
        st.markdown("**Reference translation**")
        st.success(st.session_state[ref_key])
        if st.button("Save machine translation as reference", key=f"save_ref_{paper['id']}"):
            save_translation_practice(
                int(paper["id"]),
                source_text,
                "",
                reference_translation=st.session_state[ref_key],
                self_score=None,
                notes="Machine translation reference",
            )
            st.success("Reference saved.")

    recent = list_translation_practice(limit=8)
    if recent:
        st.markdown("### Recent practice")
        df = pd.DataFrame(recent)
        visible = ["created_at", "paper_title", "self_score", "source_text", "user_translation", "notes"]
        st.dataframe(df[[c for c in visible if c in df.columns]], use_container_width=True, hide_index=True)


def run_training_page() -> None:
    st.markdown("# Training")
    st.caption("A small 不背单词-style study room for academic terms, plus abstract translation practice.")
    tab_vocab, tab_translate = st.tabs(["Vocabulary review", "Translation practice"])
    with tab_vocab:
        render_vocab_training()
    with tab_translate:
        render_translation_training()


def run_dashboard_page() -> None:
    st.markdown("# Dashboard")
    st.caption("Overview of your literature workflow, reading progress, and vocabulary training.")

    stats = get_dashboard_stats()
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Papers", stats["total_papers"])
    col2.metric("High-value cards", stats["total_cards"])
    col3.metric("Read", stats["read_papers"])
    col4.metric("Notes", stats["total_notes"])
    col5.metric("Words", stats["total_words"])
    col6.metric("Due today", stats["due_words"])

    st.divider()
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("### Papers by project")
        if stats["project_counts"]:
            df = pd.DataFrame(stats["project_counts"])
            fig = px.bar(df, x="project", y="count", text="count")
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state("No project data.", "Save papers with project labels first.")

    with chart_col2:
        st.markdown("### Priority distribution")
        if stats["priority_counts"]:
            df = pd.DataFrame(stats["priority_counts"])
            fig = px.pie(df, names="priority", values="count", hole=0.45)
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state("No priority data.", "Save papers first.")

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        st.markdown("### Papers by type")
        if stats["type_counts"]:
            df = pd.DataFrame(stats["type_counts"])
            fig = px.bar(df, x="paper_type", y="count", text="count")
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state("No type data.", "Run searches and save papers first.")

    with chart_col4:
        st.markdown("### Papers by year")
        if stats["year_counts"]:
            df = pd.DataFrame(stats["year_counts"])
            fig = px.line(df, x="year", y="count", markers=True)
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state("No year data.", "Save papers with publication year first.")

    st.divider()
    st.markdown("### Recent papers")
    recent = list_papers(order_by="created_at DESC", limit=5)
    if not recent:
        render_empty_state("No recent papers.", "Your latest saved papers will appear here.")
    else:
        for paper in recent:
            with st.container(border=True):
                title = display_value(paper.get("title"))
                url = display_value(paper.get("url"))
                if url != "N/A":
                    st.markdown(f"#### [{title}]({url})")
                else:
                    st.markdown(f"#### {title}")
                render_paper_metadata(paper)
                render_badges(paper.get("auto_tags"))
                st.caption(f"{display_value(paper.get('project'))} · {display_value(paper.get('paper_type'))} · {display_value(paper.get('priority'))} · Score {display_value(paper.get('triage_score'))}")


def run_about_page() -> None:
    st.markdown("# About PaperMate")
    st.markdown(
        """
PaperMate Lit Assistant is no longer positioned as a Zotero clone. It is a lightweight research-reading workflow tool for undergraduate research training.

### Core idea

Zotero manages papers. PaperMate helps you **screen papers, read papers, turn papers into reusable research material, and train academic English while reading**.

### What this version demonstrates

- Multi-source open literature search: Semantic Scholar, arXiv, PubMed, and bioRxiv via Europe PMC
- Project-based local paper library with SQLite
- Heuristic paper triage: paper type, reading priority, score, reason, and keywords
- Structured reading cards for research question, method, data, findings, limitations, reusable points, citation usage, and personal judgement
- Literature matrix export for review writing and group-meeting comparison
- Weekly reading report export
- Local PDF attachment and abstract reader
- Optional abstract translation with `deep-translator`
- Academic vocabulary notebook
- 不背单词-style spaced repetition: reveal meaning, Again/Hard/Good/Easy, next-review scheduling
- Abstract translation practice with saved attempts

### Why Google Scholar, Web of Science, and CNKI are not directly scraped

Google Scholar does not provide an official free public search API. Web of Science metadata access normally requires institutional subscription or Clarivate API credentials. CNKI also does not provide a stable free public API for this kind of local app. This project therefore provides external search shortcuts and leaves room for manual import, rather than using fragile or non-compliant scraping.

### Suggested GitHub positioning

> A lightweight research-reading workflow tool for undergraduate research training. It helps users search papers, triage relevance, create structured reading cards, maintain a project-based literature library, export literature matrices and weekly reading reports, and learn academic vocabulary while reading.

### Sample workflow

1. Search papers from open sources.
2. Save useful papers with project, category, and priority.
3. Use the triage board to decide which papers deserve deep reading.
4. Open Reader, translate abstracts, attach PDFs, and create structured reading cards.
5. Add unfamiliar words to Vocabulary.
6. Use Training for spaced repetition and abstract translation practice.
7. Export literature matrix or weekly reading report for group meetings, project tracking, and manuscript preparation.
"""
    )


def main() -> None:
    page = sidebar_navigation()
    if page == "Search Papers":
        run_search_page()
    elif page == "Library":
        run_library_page()
    elif page == "Reader":
        run_reader_page()
    elif page == "Research Workflow":
        run_research_workflow_page()
    elif page == "Vocabulary":
        run_vocabulary_page()
    elif page == "Training":
        run_training_page()
    elif page == "Dashboard":
        run_dashboard_page()
    elif page == "About":
        run_about_page()


if __name__ == "__main__":
    main()
