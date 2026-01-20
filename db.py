import os
import sqlite3
from typing import Any, Dict, List, Optional

import streamlit as st

# Postgres (Supabase)
import psycopg
from psycopg.rows import dict_row


# ---------- Connection helpers ----------

def _get_db_url() -> str:
    # Prefer Streamlit Cloud secrets, fallback to env for local
    url = ""
    try:
        if "SUPABASE_DB_URL" in st.secrets:
            url = st.secrets["SUPABASE_DB_URL"]
    except Exception:
        pass

    if not url:
        url = os.getenv("SUPABASE_DB_URL", "")

    return (url or "").strip()


def _get_user_email() -> str:
    # app.py should set st.session_state["current_user_email"]
    # fallback keeps app from crashing
    email = st.session_state.get("current_user_email", "default").strip().lower()
    return email or "default"


def _pg_conn():
    url = _get_db_url()
    if not url:
        raise RuntimeError("Missing SUPABASE_DB_URL. Add it to Streamlit Secrets.")
    return psycopg.connect(url, row_factory=dict_row)


# ---------- Schema init (safe) ----------

def init_db():
    """
    On Postgres, we assume tables are created in Supabase SQL editor.
    This function just validates connectivity.
    """
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1;")
                _ = cur.fetchone()
    except Exception as e:
        raise RuntimeError(f"Could not connect to Supabase/Postgres: {e}")


# ---------- Resumes ----------

def insert_resume(name: str, resume_text: str) -> int:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into resumes (user_email, name, resume_text)
                values (%s, %s, %s)
                returning id;
                """,
                (user_email, name.strip(), resume_text),
            )
            rid = cur.fetchone()["id"]
        conn.commit()
    return int(rid)


def list_resumes() -> List[Dict[str, Any]]:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, created_at
                from resumes
                where user_email = %s
                order by id desc;
                """,
                (user_email,),
            )
            return list(cur.fetchall())


def get_resume(resume_id: int) -> Dict[str, Any]:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name, resume_text, created_at
                from resumes
                where user_email = %s and id = %s
                limit 1;
                """,
                (user_email, int(resume_id)),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError("Resume not found.")
            return dict(row)


# ---------- Jobs ----------

def insert_job(company: str, title: str, location: str, url: str, jd_text: str, status: str = "Target") -> int:
    """
    company is used as the "Job Name" in your UI.
    """
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into jobs (user_email, company, title, location, url, jd_text, status)
                values (%s, %s, %s, %s, %s, %s, %s)
                returning id;
                """,
                (user_email, company.strip(), title.strip(), location.strip(), url.strip(), jd_text, status),
            )
            jid = cur.fetchone()["id"]
        conn.commit()
    return int(jid)


def list_jobs() -> List[Dict[str, Any]]:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, company, title, location, url, status,
                       applied_date, followup_date, finished_date, finished_outcome, notes, created_at
                from jobs
                where user_email = %s
                order by id desc;
                """,
                (user_email,),
            )
            return list(cur.fetchall())


def get_job(job_id: int) -> Dict[str, Any]:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from jobs
                where user_email = %s and id = %s
                limit 1;
                """,
                (user_email, int(job_id)),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError("Job not found.")
            return dict(row)


def update_job_status(job_id: int, status: str, status_date=None):
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update jobs
                set status = %s,
                    status_date = %s
                where user_email = %s and id = %s;
                """,
                (status, status_date, user_email, int(job_id)),
            )
        conn.commit()


def update_job_reporting_dates(
    job_id: int,
    applied_date=None,
    followup_date=None,
    finished_date=None,
    finished_outcome: str = "",
    notes: str = "",
):
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update jobs
                set applied_date = %s,
                    followup_date = %s,
                    finished_date = %s,
                    finished_outcome = %s,
                    notes = %s
                where user_email = %s and id = %s;
                """,
                (applied_date, followup_date, finished_date, finished_outcome.strip(), notes.strip(), user_email, int(job_id)),
            )
        conn.commit()


# ---------- Versions ----------

def insert_version(
    job_id: int,
    base_resume_id: int,
    version_name: str,
    tailored_resume: str,
    changes_summary: str,
    suggested_additions: str,
    accuracy_checklist: str,
) -> int:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into versions
                  (user_email, job_id, base_resume_id, version_name, tailored_resume,
                   changes_summary, suggested_additions, accuracy_checklist)
                values
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                returning id;
                """,
                (
                    user_email,
                    int(job_id),
                    int(base_resume_id),
                    version_name.strip(),
                    tailored_resume,
                    changes_summary,
                    suggested_additions,
                    accuracy_checklist,
                ),
            )
            vid = cur.fetchone()["id"]
        conn.commit()
    return int(vid)


def list_versions_for_job(job_id: int) -> List[Dict[str, Any]]:
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select v.id, v.version_name, v.tailored_resume, v.created_at,
                       r.name as resume_name
                from versions v
                join resumes r on r.id = v.base_resume_id
                where v.user_email = %s and v.job_id = %s
                order by v.id desc;
                """,
                (user_email, int(job_id)),
            )
            return list(cur.fetchall())


# ---------- Reports helpers ----------

def jobs_report_rows() -> List[Dict[str, Any]]:
    """
    Used by Reports tab to export a full jobs table.
    """
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  id as "Job ID",
                  company as "Job Name",
                  title as "Title",
                  location as "Location",
                  url as "URL",
                  status as "Status",
                  to_char(applied_date, 'MM/DD/YYYY') as "Applied Date",
                  to_char(followup_date, 'MM/DD/YYYY') as "Follow up Date",
                  to_char(finished_date, 'MM/DD/YYYY') as "Finished Date",
                  finished_outcome as "Finished Outcome",
                  notes as "Notes",
                  to_char(created_at, 'MM/DD/YYYY') as "Created Date"
                from jobs
                where user_email = %s
                order by id desc;
                """,
                (user_email,),
            )
            return list(cur.fetchall())


def followups_due_rows(today):
    user_email = _get_user_email()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, company, title, followup_date, status
                from jobs
                where user_email = %s
                  and followup_date is not null
                  and followup_date <= %s
                order by followup_date asc
                """,
                (user_email, today),
            )
            return cur.fetchall()



