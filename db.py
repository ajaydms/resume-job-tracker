import sqlite3
from pathlib import Path

DB_PATH = Path("jobs.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def init_db():
    conn = _connect()
    cur = conn.cursor()

    # resumes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        resume_text TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """)

    # jobs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,              -- we use this as "Job Name" label
        title TEXT,
        location TEXT,
        url TEXT,
        jd_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Target',
        status_date TEXT,                  -- <-- NEW: date corresponding to current status
        applied_date TEXT,
        followup_date TEXT,
        finished_date TEXT,
        finished_outcome TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """)

    # versions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        base_resume_id INTEGER NOT NULL,
        version_name TEXT NOT NULL,
        tailored_resume TEXT NOT NULL,
        changes_summary TEXT,
        suggested_additions TEXT,
        accuracy_checklist TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(base_resume_id) REFERENCES resumes(id)
    )
    """)

    # ---- Migrations (for older DBs) ----
    for col, ddl in [
        ("status_date", "ALTER TABLE jobs ADD COLUMN status_date TEXT"),
        ("applied_date", "ALTER TABLE jobs ADD COLUMN applied_date TEXT"),
        ("followup_date", "ALTER TABLE jobs ADD COLUMN followup_date TEXT"),
        ("finished_date", "ALTER TABLE jobs ADD COLUMN finished_date TEXT"),
        ("finished_outcome", "ALTER TABLE jobs ADD COLUMN finished_outcome TEXT"),
        ("notes", "ALTER TABLE jobs ADD COLUMN notes TEXT"),
    ]:
        if not _column_exists(conn, "jobs", col):
            cur.execute(ddl)

    conn.commit()
    conn.close()


# ---------- Resumes ----------
def insert_resume(name: str, resume_text: str) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO resumes(name, resume_text) VALUES (?, ?)", (name, resume_text))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def list_resumes():
    conn = _connect()
    rows = conn.execute("SELECT id, name FROM resumes ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def get_resume(resume_id: int):
    conn = _connect()
    row = conn.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()
    conn.close()
    return row


# ---------- Jobs ----------
def insert_job(company: str, title: str, location: str, url: str, jd_text: str) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO jobs(company, title, location, url, jd_text)
        VALUES (?, ?, ?, ?, ?)
    """, (company, title, location, url, jd_text))
    conn.commit()
    jid = cur.lastrowid
    conn.close()
    return jid


def list_jobs():
    conn = _connect()
    rows = conn.execute("SELECT id, company, status FROM jobs ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def get_job(job_id: int):
    conn = _connect()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return row


def update_job_status(job_id: int, status: str, status_date: str = ""):
    """
    status_date should be ISO date string YYYY-MM-DD or "".
    We also auto-fill applied_date/finished_date when relevant.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute("UPDATE jobs SET status=?, status_date=? WHERE id=?", (status, status_date, job_id))

    # If status is Applied and applied_date isn't set, set it
    if status == "Applied" and status_date:
        cur.execute("""
            UPDATE jobs
            SET applied_date = CASE WHEN applied_date IS NULL OR applied_date='' THEN ? ELSE applied_date END
            WHERE id=?
        """, (status_date, job_id))

    # If status is Finished and finished_date isn't set, set it
    if status == "Finished" and status_date:
        cur.execute("""
            UPDATE jobs
            SET finished_date = CASE WHEN finished_date IS NULL OR finished_date='' THEN ? ELSE finished_date END
            WHERE id=?
        """, (status_date, job_id))

    conn.commit()
    conn.close()


def update_job_dates(job_id: int, applied_date: str, followup_date: str, finished_date: str, finished_outcome: str, notes: str):
    conn = _connect()
    conn.execute("""
        UPDATE jobs
        SET applied_date=?, followup_date=?, finished_date=?, finished_outcome=?, notes=?
        WHERE id=?
    """, (applied_date, followup_date, finished_date, finished_outcome, notes, job_id))
    conn.commit()
    conn.close()


# ---------- Versions ----------
def insert_version(job_id: int, base_resume_id: int, version_name: str, tailored_resume: str,
                   changes_summary: str, suggested_additions: str, accuracy_checklist: str) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO versions(job_id, base_resume_id, version_name, tailored_resume, changes_summary, suggested_additions, accuracy_checklist)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (job_id, base_resume_id, version_name, tailored_resume, changes_summary, suggested_additions, accuracy_checklist))
    conn.commit()
    vid = cur.lastrowid
    conn.close()
    return vid


def list_versions_for_job(job_id: int):
    conn = _connect()
    rows = conn.execute("""
        SELECT v.*, r.name AS resume_name
        FROM versions v
        JOIN resumes r ON r.id = v.base_resume_id
        WHERE v.job_id=?
        ORDER BY v.id DESC
    """, (job_id,)).fetchall()
    conn.close()
    return rows


# ---------- Reporting ----------
def jobs_report_rows():
    conn = _connect()
    rows = conn.execute("""
        SELECT id, company, status, status_date, applied_date, followup_date, finished_date, finished_outcome, notes, created_at
        FROM jobs
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows


def followups_due_rows(today_iso: str):
    conn = _connect()
    rows = conn.execute("""
        SELECT id, company, status, followup_date
        FROM jobs
        WHERE followup_date IS NOT NULL
          AND followup_date <> ''
          AND followup_date <= ?
          AND status <> 'Finished'
        ORDER BY followup_date ASC
    """, (today_iso,)).fetchall()
    conn.close()
    return rows
