import sqlite3

import os

DB_NAME = os.path.join(os.path.dirname(__file__), "jobs.db")



# ---------- Database Setup ----------
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                company TEXT,
                location TEXT,
                description TEXT,
                UNIQUE(title, company, location)  -- prevent duplicates
            )
        """)

        conn.commit()


# ---------- Insert / Update ----------
def save_jobs(jobs):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        for job in jobs:
            title = job.get("title")
            company = job.get("company")
            location = job.get("location")
            description = job.get("description", "")

            # Use INSERT OR IGNORE to avoid yellow duplicates
            c.execute("""
                INSERT OR IGNORE INTO jobs (title, company, location, description)
                VALUES (?, ?, ?, ?)
            """, (title, company, location, description))

        conn.commit()


# ---------- Query Helpers ----------
def get_all_jobs():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row  # enables dict-style access
        c = conn.cursor()

        c.execute("SELECT * FROM jobs ORDER BY id DESC")
        rows = c.fetchall()

        return [dict(row) for row in rows]


def get_job_by_id(job_id):
    """Useful if you later want a dedicated job details page"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = c.fetchone()

        return dict(row) if row else None
