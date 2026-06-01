from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from src.utils import make_unique_key, normalize_paper_record

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "papermate.db"

PAPER_COLUMNS = {
    "source": "TEXT",
    "paper_id": "TEXT",
    "title": "TEXT NOT NULL",
    "authors": "TEXT",
    "year": "INTEGER",
    "publication_date": "TEXT",
    "venue": "TEXT",
    "journal": "TEXT",
    "abstract": "TEXT",
    "doi": "TEXT",
    "url": "TEXT",
    "citation_count": "INTEGER",
    "category": "TEXT DEFAULT 'Other'",
    "project": "TEXT DEFAULT 'General Reading'",
    "status": "TEXT DEFAULT '待读'",
    "notes": "TEXT DEFAULT ''",
    "field": "TEXT",
    "impact_factor": "TEXT",
    "affiliations": "TEXT",
    "auto_tags": "TEXT",
    "translated_abstract": "TEXT",
    "pdf_path": "TEXT",
    "paper_type": "TEXT",
    "priority": "TEXT",
    "triage_score": "INTEGER",
    "triage_reason": "TEXT",
    "keywords": "TEXT",
    "reading_time_estimate": "TEXT",
    "unique_key": "TEXT UNIQUE",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}

VOCAB_COLUMNS = {
    "word": "TEXT NOT NULL",
    "meaning": "TEXT",
    "source_title": "TEXT",
    "example_sentence": "TEXT",
    "context": "TEXT",
    "notes": "TEXT",
    "difficulty": "TEXT DEFAULT 'Medium'",
    "familiarity": "INTEGER DEFAULT 0",
    "review_interval": "INTEGER DEFAULT 0",
    "ease_factor": "REAL DEFAULT 2.5",
    "review_count": "INTEGER DEFAULT 0",
    "correct_count": "INTEGER DEFAULT 0",
    "wrong_count": "INTEGER DEFAULT 0",
    "last_review_at": "TEXT",
    "next_review_at": "TEXT",
    "created_at": "TEXT",
}

READING_CARD_COLUMNS = {
    "paper_id": "INTEGER UNIQUE NOT NULL",
    "research_question": "TEXT",
    "method": "TEXT",
    "data": "TEXT",
    "findings": "TEXT",
    "limitations": "TEXT",
    "reusable_points": "TEXT",
    "citation_usage": "TEXT",
    "personal_judgement": "TEXT",
    "rating": "INTEGER DEFAULT 3",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}

TRANSLATION_COLUMNS = {
    "paper_id": "INTEGER",
    "source_text": "TEXT",
    "user_translation": "TEXT",
    "reference_translation": "TEXT",
    "self_score": "INTEGER",
    "notes": "TEXT",
    "created_at": "TEXT",
}


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_iso() -> str:
    return date.today().isoformat()


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _existing_columns(conn, table)
    for column, col_type in columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                paper_id TEXT,
                title TEXT NOT NULL,
                authors TEXT,
                year INTEGER,
                publication_date TEXT,
                venue TEXT,
                journal TEXT,
                abstract TEXT,
                doi TEXT,
                url TEXT,
                citation_count INTEGER,
                category TEXT DEFAULT 'Other',
                project TEXT DEFAULT 'General Reading',
                status TEXT DEFAULT '待读',
                notes TEXT DEFAULT '',
                field TEXT,
                impact_factor TEXT,
                affiliations TEXT,
                auto_tags TEXT,
                translated_abstract TEXT,
                pdf_path TEXT,
                paper_type TEXT,
                priority TEXT,
                triage_score INTEGER,
                triage_reason TEXT,
                keywords TEXT,
                reading_time_estimate TEXT,
                unique_key TEXT UNIQUE,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        _ensure_columns(conn, "papers", PAPER_COLUMNS)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                meaning TEXT,
                source_title TEXT,
                example_sentence TEXT,
                context TEXT,
                notes TEXT,
                difficulty TEXT DEFAULT 'Medium',
                familiarity INTEGER DEFAULT 0,
                review_interval INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                review_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                last_review_at TEXT,
                next_review_at TEXT,
                created_at TEXT
            )
            """
        )
        _ensure_columns(conn, "vocabulary", VOCAB_COLUMNS)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reading_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                note_type TEXT DEFAULT 'General',
                quote TEXT,
                note TEXT,
                page TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reading_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER UNIQUE NOT NULL,
                research_question TEXT,
                method TEXT,
                data TEXT,
                findings TEXT,
                limitations TEXT,
                reusable_points TEXT,
                citation_usage TEXT,
                personal_judgement TEXT,
                rating INTEGER DEFAULT 3,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            )
            """
        )
        _ensure_columns(conn, "reading_cards", READING_CARD_COLUMNS)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_practice (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER,
                source_text TEXT,
                user_translation TEXT,
                reference_translation TEXT,
                self_score INTEGER,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE SET NULL
            )
            """
        )
        _ensure_columns(conn, "translation_practice", TRANSLATION_COLUMNS)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_category ON papers(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_project ON papers(project)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_journal ON papers(journal)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_priority ON papers(priority)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocabulary(word)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vocab_due ON vocabulary(next_review_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_paper_id ON reading_notes(paper_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_paper_id ON reading_cards(paper_id)")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def add_or_update_paper(
    paper: dict,
    category: str | None = None,
    status: str = "待读",
    notes: str = "",
    project: str | None = None,
) -> tuple[int, bool]:
    record = normalize_paper_record(paper)
    unique_key = make_unique_key(record)
    timestamp = now_iso()
    final_category = category or record.get("category") or "Other"
    final_project = project or record.get("project") or "General Reading"

    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM papers WHERE unique_key = ?", (unique_key,)).fetchone()

        values = (
            record["source"], record["paper_id"], record["title"], record["authors"], record["year"],
            record["publication_date"], record["venue"], record["journal"], record["abstract"], record["doi"],
            record["url"], record["citation_count"], final_category, final_project, status, notes,
            record["field"], record["impact_factor"], record["affiliations"], record["auto_tags"],
            record["translated_abstract"], record["pdf_path"], record["paper_type"], record["priority"],
            record["triage_score"], record["triage_reason"], record["keywords"], record["reading_time_estimate"],
        )

        if existing:
            paper_id = int(existing["id"])
            conn.execute(
                """
                UPDATE papers
                SET source = ?, paper_id = ?, title = ?, authors = ?, year = ?, publication_date = ?,
                    venue = ?, journal = ?, abstract = ?, doi = ?, url = ?, citation_count = ?,
                    category = ?, project = ?, status = ?, notes = ?, field = ?, impact_factor = ?, affiliations = ?,
                    auto_tags = ?, translated_abstract = ?, pdf_path = ?, paper_type = ?, priority = ?, triage_score = ?,
                    triage_reason = ?, keywords = ?, reading_time_estimate = ?, updated_at = ?
                WHERE id = ?
                """,
                values + (timestamp, paper_id),
            )
            return paper_id, False

        cursor = conn.execute(
            """
            INSERT INTO papers (
                source, paper_id, title, authors, year, publication_date, venue, journal, abstract, doi,
                url, citation_count, category, project, status, notes, field, impact_factor, affiliations, auto_tags,
                translated_abstract, pdf_path, paper_type, priority, triage_score, triage_reason, keywords,
                reading_time_estimate, unique_key, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values + (unique_key, timestamp, timestamp),
        )
        return int(cursor.lastrowid), True


def list_papers(
    keyword: str = "",
    category: str | None = None,
    status: str | None = None,
    source: str | None = None,
    project: str | None = None,
    priority: str | None = None,
    order_by: str = "created_at DESC",
    limit: int | None = None,
) -> list[dict]:
    allowed_order = {
        "created_at DESC", "created_at ASC", "year DESC", "year ASC", "citation_count DESC", "title ASC",
        "journal ASC", "triage_score DESC", "priority ASC", "updated_at DESC",
    }
    if order_by not in allowed_order:
        order_by = "created_at DESC"

    clauses = []
    params: list[Any] = []

    if keyword.strip():
        like = f"%{keyword.strip().lower()}%"
        clauses.append(
            """
            (
                LOWER(title) LIKE ? OR LOWER(authors) LIKE ? OR LOWER(abstract) LIKE ? OR LOWER(doi) LIKE ?
                OR LOWER(notes) LIKE ? OR LOWER(venue) LIKE ? OR LOWER(journal) LIKE ? OR LOWER(field) LIKE ?
                OR LOWER(affiliations) LIKE ? OR LOWER(auto_tags) LIKE ? OR LOWER(project) LIKE ?
                OR LOWER(keywords) LIKE ? OR LOWER(triage_reason) LIKE ?
            )
            """
        )
        params.extend([like] * 13)

    if category:
        clauses.append("category = ?")
        params.append(category)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if project:
        clauses.append("project = ?")
        params.append(project)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = "LIMIT ?" if limit else ""
    if limit:
        params.append(limit)

    sql = f"""
        SELECT *
        FROM papers
        {where_sql}
        ORDER BY {order_by}
        {limit_sql}
    """

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows]


def get_paper(paper_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    return row_to_dict(row) if row else None


def update_paper(
    paper_id: int,
    category: str,
    status: str,
    notes: str,
    field: str = "",
    impact_factor: str = "",
    affiliations: str = "",
    auto_tags: str = "",
    translated_abstract: str = "",
    pdf_path: str = "",
    project: str = "General Reading",
    paper_type: str = "Other",
    priority: str = "Medium",
    triage_score: int | None = None,
    triage_reason: str = "",
    keywords: str = "",
    reading_time_estimate: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE papers
            SET category = ?, project = ?, status = ?, notes = ?, field = ?, impact_factor = ?, affiliations = ?,
                auto_tags = ?, translated_abstract = ?, pdf_path = ?, paper_type = ?, priority = ?, triage_score = ?,
                triage_reason = ?, keywords = ?, reading_time_estimate = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                category, project, status, notes, field, impact_factor, affiliations, auto_tags, translated_abstract,
                pdf_path, paper_type, priority, triage_score, triage_reason, keywords, reading_time_estimate, now_iso(), paper_id,
            ),
        )


def update_pdf_path(paper_id: int, pdf_path: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE papers SET pdf_path = ?, updated_at = ? WHERE id = ?", (pdf_path, now_iso(), paper_id))


def update_translated_abstract(paper_id: int, translated_abstract: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE papers SET translated_abstract = ?, updated_at = ? WHERE id = ?", (translated_abstract, now_iso(), paper_id))


def delete_paper(paper_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM reading_notes WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM reading_cards WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM translation_practice WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))


def add_vocabulary(
    word: str,
    meaning: str = "",
    source_title: str = "",
    notes: str = "",
    example_sentence: str = "",
    context: str = "",
    difficulty: str = "Medium",
) -> int:
    timestamp = now_iso()
    next_review = today_iso()
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM vocabulary WHERE LOWER(word) = LOWER(?)", (word.strip(),)).fetchone()
        if existing:
            vocab_id = int(existing["id"])
            conn.execute(
                """
                UPDATE vocabulary
                SET meaning = COALESCE(NULLIF(?, ''), meaning),
                    source_title = COALESCE(NULLIF(?, ''), source_title),
                    example_sentence = COALESCE(NULLIF(?, ''), example_sentence),
                    context = COALESCE(NULLIF(?, ''), context),
                    notes = COALESCE(NULLIF(?, ''), notes),
                    difficulty = COALESCE(NULLIF(?, ''), difficulty)
                WHERE id = ?
                """,
                (meaning.strip(), source_title.strip(), example_sentence.strip(), context.strip(), notes.strip(), difficulty, vocab_id),
            )
            return vocab_id

        cursor = conn.execute(
            """
            INSERT INTO vocabulary (
                word, meaning, source_title, example_sentence, context, notes, difficulty, familiarity,
                review_interval, ease_factor, review_count, correct_count, wrong_count, last_review_at, next_review_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 2.5, 0, 0, 0, NULL, ?, ?)
            """,
            (word.strip(), meaning.strip(), source_title.strip(), example_sentence.strip(), context.strip(), notes.strip(), difficulty, next_review, timestamp),
        )
        return int(cursor.lastrowid)


def list_vocabulary(keyword: str = "", due_only: bool = False, limit: int | None = None) -> list[dict]:
    params: list[Any] = []
    clauses = []

    if keyword.strip():
        like = f"%{keyword.strip().lower()}%"
        clauses.append(
            """
            (LOWER(word) LIKE ? OR LOWER(meaning) LIKE ? OR LOWER(source_title) LIKE ? OR LOWER(notes) LIKE ?
             OR LOWER(example_sentence) LIKE ? OR LOWER(context) LIKE ?)
            """
        )
        params.extend([like] * 6)
    if due_only:
        clauses.append("(next_review_at IS NULL OR next_review_at <= ?)")
        params.append(today_iso())

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = "LIMIT ?" if limit else ""
    if limit:
        params.append(limit)

    sql = f"SELECT * FROM vocabulary {where_sql} ORDER BY COALESCE(next_review_at, '1900-01-01') ASC, created_at DESC {limit_sql}"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows]


def get_vocabulary(vocab_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM vocabulary WHERE id = ?", (vocab_id,)).fetchone()
    return row_to_dict(row) if row else None


def update_vocabulary(
    vocab_id: int,
    word: str,
    meaning: str = "",
    source_title: str = "",
    notes: str = "",
    example_sentence: str = "",
    context: str = "",
    difficulty: str = "Medium",
    familiarity: int | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE vocabulary
            SET word = ?, meaning = ?, source_title = ?, example_sentence = ?, context = ?, notes = ?,
                difficulty = ?, familiarity = COALESCE(?, familiarity)
            WHERE id = ?
            """,
            (word.strip(), meaning.strip(), source_title.strip(), example_sentence.strip(), context.strip(), notes.strip(), difficulty, familiarity, vocab_id),
        )


def review_vocabulary(vocab_id: int, grade: str) -> None:
    grade = grade.lower()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM vocabulary WHERE id = ?", (vocab_id,)).fetchone()
        if not row:
            return
        interval = int(row["review_interval"] or 0)
        ease = float(row["ease_factor"] or 2.5)
        familiarity = int(row["familiarity"] or 0)
        review_count = int(row["review_count"] or 0) + 1
        correct_count = int(row["correct_count"] or 0)
        wrong_count = int(row["wrong_count"] or 0)

        if grade == "again":
            interval = 0
            ease = max(1.3, ease - 0.25)
            familiarity = max(0, familiarity - 1)
            wrong_count += 1
            next_days = 0
        elif grade == "hard":
            interval = max(1, interval)
            ease = max(1.3, ease - 0.1)
            familiarity = min(5, familiarity + 1)
            correct_count += 1
            next_days = 1
        elif grade == "easy":
            interval = max(3, int((interval or 1) * (ease + 0.8)))
            ease = min(3.2, ease + 0.15)
            familiarity = min(5, familiarity + 2)
            correct_count += 1
            next_days = interval
        else:
            interval = 1 if interval == 0 else max(2, int(interval * ease))
            familiarity = min(5, familiarity + 1)
            correct_count += 1
            next_days = interval

        next_review = (date.today() + timedelta(days=next_days)).isoformat()
        conn.execute(
            """
            UPDATE vocabulary
            SET review_interval = ?, ease_factor = ?, familiarity = ?, review_count = ?, correct_count = ?, wrong_count = ?,
                last_review_at = ?, next_review_at = ?
            WHERE id = ?
            """,
            (interval, ease, familiarity, review_count, correct_count, wrong_count, now_iso(), next_review, vocab_id),
        )


def delete_vocabulary(vocab_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM vocabulary WHERE id = ?", (vocab_id,))


def add_reading_note(paper_id: int, note_type: str, quote: str, note: str, page: str = "") -> int:
    timestamp = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reading_notes (paper_id, note_type, quote, note, page, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (paper_id, note_type, quote.strip(), note.strip(), page.strip(), timestamp, timestamp),
        )
        return int(cursor.lastrowid)


def list_reading_notes(paper_id: int | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    clauses = []
    params: list[Any] = []
    if paper_id is not None:
        clauses.append("rn.paper_id = ?")
        params.append(paper_id)
    if start_date:
        clauses.append("DATE(rn.created_at) >= DATE(?)")
        params.append(start_date)
    if end_date:
        clauses.append("DATE(rn.created_at) <= DATE(?)")
        params.append(end_date)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT rn.*, p.title AS paper_title, p.project AS project, p.category AS category
        FROM reading_notes rn
        LEFT JOIN papers p ON p.id = rn.paper_id
        {where_sql}
        ORDER BY rn.created_at DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows]


def delete_reading_note(note_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM reading_notes WHERE id = ?", (note_id,))


def get_reading_card(paper_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM reading_cards WHERE paper_id = ?", (paper_id,)).fetchone()
    return row_to_dict(row) if row else None


def upsert_reading_card(
    paper_id: int,
    research_question: str = "",
    method: str = "",
    data: str = "",
    findings: str = "",
    limitations: str = "",
    reusable_points: str = "",
    citation_usage: str = "",
    personal_judgement: str = "",
    rating: int = 3,
) -> int:
    timestamp = now_iso()
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM reading_cards WHERE paper_id = ?", (paper_id,)).fetchone()
        if existing:
            card_id = int(existing["id"])
            conn.execute(
                """
                UPDATE reading_cards
                SET research_question = ?, method = ?, data = ?, findings = ?, limitations = ?, reusable_points = ?,
                    citation_usage = ?, personal_judgement = ?, rating = ?, updated_at = ?
                WHERE id = ?
                """,
                (research_question, method, data, findings, limitations, reusable_points, citation_usage, personal_judgement, rating, timestamp, card_id),
            )
            return card_id
        cursor = conn.execute(
            """
            INSERT INTO reading_cards (
                paper_id, research_question, method, data, findings, limitations, reusable_points,
                citation_usage, personal_judgement, rating, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (paper_id, research_question, method, data, findings, limitations, reusable_points, citation_usage, personal_judgement, rating, timestamp, timestamp),
        )
        return int(cursor.lastrowid)


def list_reading_cards(project: str | None = None, category: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    clauses = []
    params: list[Any] = []
    if project:
        clauses.append("p.project = ?")
        params.append(project)
    if category:
        clauses.append("p.category = ?")
        params.append(category)
    if start_date:
        clauses.append("DATE(rc.updated_at) >= DATE(?)")
        params.append(start_date)
    if end_date:
        clauses.append("DATE(rc.updated_at) <= DATE(?)")
        params.append(end_date)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT rc.*, p.title, p.authors, p.year, p.journal, p.category, p.project, p.priority, p.paper_type, p.keywords, p.status
        FROM reading_cards rc
        LEFT JOIN papers p ON p.id = rc.paper_id
        {where_sql}
        ORDER BY rc.updated_at DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows]


def save_translation_practice(
    paper_id: int | None,
    source_text: str,
    user_translation: str,
    reference_translation: str = "",
    self_score: int | None = None,
    notes: str = "",
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO translation_practice (paper_id, source_text, user_translation, reference_translation, self_score, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (paper_id, source_text.strip(), user_translation.strip(), reference_translation.strip(), self_score, notes.strip(), now_iso()),
        )
        return int(cursor.lastrowid)


def list_translation_practice(limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT tp.*, p.title AS paper_title
            FROM translation_practice tp
            LEFT JOIN papers p ON p.id = tp.paper_id
            ORDER BY tp.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_dashboard_stats() -> dict:
    with get_connection() as conn:
        total_papers = conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
        favorite_papers = conn.execute("SELECT COUNT(*) AS n FROM papers WHERE status = '收藏'").fetchone()["n"]
        read_papers = conn.execute("SELECT COUNT(*) AS n FROM papers WHERE status = '已读'").fetchone()["n"]
        total_words = conn.execute("SELECT COUNT(*) AS n FROM vocabulary").fetchone()["n"]
        due_words = conn.execute("SELECT COUNT(*) AS n FROM vocabulary WHERE next_review_at IS NULL OR next_review_at <= ?", (today_iso(),)).fetchone()["n"]
        total_notes = conn.execute("SELECT COUNT(*) AS n FROM reading_notes").fetchone()["n"]
        total_cards = conn.execute("SELECT COUNT(*) AS n FROM reading_cards").fetchone()["n"]
        total_translation_practice = conn.execute("SELECT COUNT(*) AS n FROM translation_practice").fetchone()["n"]

        category_rows = conn.execute("""
            SELECT COALESCE(category, 'Other') AS category, COUNT(*) AS count
            FROM papers GROUP BY COALESCE(category, 'Other') ORDER BY count DESC
        """).fetchall()
        status_rows = conn.execute("""
            SELECT COALESCE(status, '待读') AS status, COUNT(*) AS count
            FROM papers GROUP BY COALESCE(status, '待读') ORDER BY count DESC
        """).fetchall()
        source_rows = conn.execute("""
            SELECT COALESCE(source, 'N/A') AS source, COUNT(*) AS count
            FROM papers GROUP BY COALESCE(source, 'N/A') ORDER BY count DESC
        """).fetchall()
        year_rows = conn.execute("""
            SELECT year, COUNT(*) AS count FROM papers WHERE year IS NOT NULL GROUP BY year ORDER BY year ASC
        """).fetchall()
        project_rows = conn.execute("""
            SELECT COALESCE(project, 'General Reading') AS project, COUNT(*) AS count
            FROM papers GROUP BY COALESCE(project, 'General Reading') ORDER BY count DESC
        """).fetchall()
        priority_rows = conn.execute("""
            SELECT COALESCE(priority, 'N/A') AS priority, COUNT(*) AS count
            FROM papers GROUP BY COALESCE(priority, 'N/A') ORDER BY count DESC
        """).fetchall()
        type_rows = conn.execute("""
            SELECT COALESCE(paper_type, 'Other') AS paper_type, COUNT(*) AS count
            FROM papers GROUP BY COALESCE(paper_type, 'Other') ORDER BY count DESC
        """).fetchall()
        vocab_rows = conn.execute("""
            SELECT COALESCE(difficulty, 'Medium') AS difficulty, COUNT(*) AS count
            FROM vocabulary GROUP BY COALESCE(difficulty, 'Medium') ORDER BY count DESC
        """).fetchall()

    return {
        "total_papers": total_papers,
        "favorite_papers": favorite_papers,
        "read_papers": read_papers,
        "total_words": total_words,
        "due_words": due_words,
        "total_notes": total_notes,
        "total_cards": total_cards,
        "total_translation_practice": total_translation_practice,
        "category_counts": [row_to_dict(row) for row in category_rows],
        "status_counts": [row_to_dict(row) for row in status_rows],
        "source_counts": [row_to_dict(row) for row in source_rows],
        "year_counts": [row_to_dict(row) for row in year_rows],
        "project_counts": [row_to_dict(row) for row in project_rows],
        "priority_counts": [row_to_dict(row) for row in priority_rows],
        "type_counts": [row_to_dict(row) for row in type_rows],
        "vocab_difficulty_counts": [row_to_dict(row) for row in vocab_rows],
    }
