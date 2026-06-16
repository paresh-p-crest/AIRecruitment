"""Async SQLAlchemy engine and session setup for SQLite."""

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./recruitment.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def _migrate_app_settings(connection) -> None:
    """Add new columns to app_settings for existing SQLite databases."""
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    if "app_settings" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("app_settings")}
    if "google_api_key" not in columns:
        connection.execute(
            sa.text("ALTER TABLE app_settings ADD COLUMN google_api_key TEXT")
        )
    if "google_model" not in columns:
        connection.execute(
            sa.text(
                "ALTER TABLE app_settings ADD COLUMN google_model VARCHAR(64) "
                "DEFAULT 'gemini-2.5-flash'"
            )
        )

    # Migrate retired Gemini model IDs saved in older demo versions
    connection.execute(
        sa.text(
            "UPDATE app_settings SET google_model = 'gemini-2.5-pro' "
            "WHERE google_model = 'gemini-1.5-pro'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE app_settings SET google_model = 'gemini-2.5-flash' "
            "WHERE google_model IN ('gemini-1.5-flash', 'gemini-2.0-flash')"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE app_settings SET google_model = 'gemini-2.5-flash-lite' "
            "WHERE google_model IN ('gemini-1.5-flash-lite', 'gemini-2.0-flash-lite')"
        )
    )


def _migrate_resumes(connection) -> None:
    """Add duplicate-detection columns to resumes for existing SQLite databases."""
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    if "resumes" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("resumes")}
    if "file_hash" not in columns:
        connection.execute(sa.text("ALTER TABLE resumes ADD COLUMN file_hash VARCHAR(64)"))
    if "candidate_email" not in columns:
        connection.execute(
            sa.text("ALTER TABLE resumes ADD COLUMN candidate_email VARCHAR(320)")
        )

    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_resumes_file_hash ON resumes (file_hash)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_resumes_candidate_email "
            "ON resumes (candidate_email)"
        )
    )

    connection.execute(
        sa.text(
            "UPDATE resumes SET candidate_email = lower(trim("
            "json_extract(extracted_data, '$.Personal_Info.Email'))) "
            "WHERE candidate_email IS NULL "
            "AND json_extract(extracted_data, '$.Personal_Info.Email') IS NOT NULL "
            "AND instr(json_extract(extracted_data, '$.Personal_Info.Email'), '@') > 0"
        )
    )


def _migrate_job_and_matching(connection) -> None:
    """Ensure job description and match result tables exist for older databases."""
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if "job_descriptions" not in tables:
        connection.execute(
            sa.text(
                "CREATE TABLE job_descriptions ("
                "id INTEGER PRIMARY KEY, "
                "raw_text TEXT NOT NULL DEFAULT '', "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
            )
        )
        connection.execute(
            sa.text("INSERT INTO job_descriptions (id, raw_text) VALUES (1, '')")
        )

    if "match_results" not in tables:
        connection.execute(
            sa.text(
                "CREATE TABLE match_results ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "resume_id INTEGER NOT NULL UNIQUE, "
                "candidate_name VARCHAR(256), "
                "filename VARCHAR(512), "
                "rank INTEGER, "
                "final_score FLOAT NOT NULL DEFAULT 0, "
                "component_scores JSON NOT NULL, "
                "matching_skills JSON NOT NULL, "
                "missing_skills JSON NOT NULL, "
                "red_flags JSON NOT NULL, "
                "red_flag_penalty FLOAT NOT NULL DEFAULT 0, "
                "strengths JSON NOT NULL, "
                "weaknesses JSON NOT NULL, "
                "summary TEXT NOT NULL DEFAULT '', "
                "matched_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                "FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE)"
            )
        )
        connection.execute(
            sa.text("CREATE INDEX IF NOT EXISTS ix_match_results_rank ON match_results (rank)")
        )


def _backfill_job_titles(connection) -> None:
    """Normalize stored titles to short single-line labels."""
    import sqlalchemy as sa

    from jd_service import derive_job_title
    from jd_parser import parse_job_description

    rows = connection.execute(
        sa.text("SELECT id, raw_text, title FROM job_descriptions")
    ).fetchall()
    for job_id, raw_text, title in rows:
        raw = raw_text or ""
        parsed = parse_job_description(raw)
        current = (title or "").strip()
        needs_fix = (
            not current
            or "\n" in current
            or len(current) > 80
            or current.lower().startswith("min.")
        )
        if not needs_fix:
            continue
        new_title = derive_job_title(raw, parsed)
        connection.execute(
            sa.text("UPDATE job_descriptions SET title = :title WHERE id = :id"),
            {"title": new_title, "id": job_id},
        )


def _migrate_multi_job_descriptions(connection) -> None:
    """Support multiple job postings and per-job match history."""
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if "job_descriptions" in tables:
        columns = {col["name"] for col in inspector.get_columns("job_descriptions")}
        if "title" not in columns:
            connection.execute(
                sa.text("ALTER TABLE job_descriptions ADD COLUMN title VARCHAR(256)")
            )
        if "is_active" not in columns:
            connection.execute(
                sa.text(
                    "ALTER TABLE job_descriptions ADD COLUMN is_active BOOLEAN "
                    "NOT NULL DEFAULT 0"
                )
            )
        if "created_at" not in columns:
            connection.execute(
                sa.text("ALTER TABLE job_descriptions ADD COLUMN created_at DATETIME")
            )
            connection.execute(
                sa.text(
                    "UPDATE job_descriptions SET created_at = updated_at "
                    "WHERE created_at IS NULL"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE job_descriptions SET created_at = CURRENT_TIMESTAMP "
                    "WHERE created_at IS NULL"
                )
            )

        row_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM job_descriptions")
        ).scalar()
        if row_count == 0:
            connection.execute(
                sa.text(
                    "INSERT INTO job_descriptions (id, raw_text, is_active) "
                    "VALUES (1, '', 1)"
                )
            )
        else:
            active_count = connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM job_descriptions WHERE is_active = 1"
                )
            ).scalar()
            if not active_count:
                connection.execute(
                    sa.text(
                        "UPDATE job_descriptions SET is_active = 1 "
                        "WHERE id = (SELECT MAX(id) FROM job_descriptions)"
                    )
                )

        connection.execute(
            sa.text(
                "UPDATE job_descriptions SET title = 'Untitled role' "
                "WHERE title IS NULL OR trim(title) = ''"
            )
        )
        _backfill_job_titles(connection)
        connection.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_job_descriptions_is_active "
                "ON job_descriptions (is_active)"
            )
        )

    if "match_results" in tables:
        columns = {col["name"] for col in inspector.get_columns("match_results")}
        if "job_description_id" not in columns:
            connection.execute(
                sa.text(
                    "ALTER TABLE match_results ADD COLUMN job_description_id INTEGER "
                    "REFERENCES job_descriptions(id) ON DELETE CASCADE"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE match_results SET job_description_id = 1 "
                    "WHERE job_description_id IS NULL"
                )
            )
            connection.execute(
                sa.text(
                    "CREATE INDEX IF NOT EXISTS ix_match_results_job_description_id "
                    "ON match_results (job_description_id)"
                )
            )


def _drop_legacy_resume_unique_index(connection) -> None:
    """Drop SQLAlchemy's old UNIQUE index on resume_id alone."""
    import sqlalchemy as sa

    rows = connection.execute(
        sa.text(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name='match_results'"
        )
    ).fetchall()
    for name, sql in rows:
        if not name or not sql:
            continue
        normalized = sql.upper()
        if (
            "UNIQUE" in normalized
            and "RESUME_ID" in normalized
            and "JOB_DESCRIPTION_ID" not in normalized
        ):
            connection.execute(sa.text(f'DROP INDEX IF EXISTS "{name}"'))

    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_match_results_resume_id "
            "ON match_results (resume_id)"
        )
    )


def _migrate_match_results_per_job_unique(connection) -> None:
    """
    Remove legacy UNIQUE(resume_id) so each resume can have one match per job.

    Rebuilds match_results when the old single-job schema is detected.
    """
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    if "match_results" not in inspector.get_table_names():
        return

    if connection.execute(
        sa.text(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='uq_match_results_job_candidate'"
        )
    ).fetchone():
        _drop_legacy_resume_unique_index(connection)
        return

    ddl_row = connection.execute(
        sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='match_results'"
        )
    ).fetchone()
    ddl = (ddl_row[0] or "") if ddl_row else ""
    needs_rebuild = "resume_id" in ddl.lower() and "unique" in ddl.lower()

    if not needs_rebuild:
        connection.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_match_results_job_candidate "
                "ON match_results (job_description_id, candidate_id)"
            )
        )
        return

    connection.execute(
        sa.text(
            "CREATE TABLE match_results_new ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "job_description_id INTEGER NOT NULL "
            "REFERENCES job_descriptions(id) ON DELETE CASCADE, "
            "candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE, "
            "resume_id INTEGER REFERENCES resumes(id) ON DELETE CASCADE, "
            "candidate_name VARCHAR(256), "
            "filename VARCHAR(512), "
            "rank INTEGER, "
            "final_score FLOAT NOT NULL DEFAULT 0, "
            "component_scores JSON NOT NULL DEFAULT '{}', "
            "matching_skills JSON NOT NULL DEFAULT '[]', "
            "missing_skills JSON NOT NULL DEFAULT '[]', "
            "red_flags JSON NOT NULL DEFAULT '[]', "
            "red_flag_penalty FLOAT NOT NULL DEFAULT 0, "
            "strengths JSON NOT NULL DEFAULT '[]', "
            "weaknesses JSON NOT NULL DEFAULT '[]', "
            "summary TEXT NOT NULL DEFAULT '', "
            "matched_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
        )
    )
    columns = {col["name"] for col in inspector.get_columns("match_results")}
    if "job_description_id" in columns:
        connection.execute(
            sa.text(
                "INSERT INTO match_results_new ("
                "id, job_description_id, candidate_id, resume_id, candidate_name, "
                "filename, rank, final_score, component_scores, matching_skills, "
                "missing_skills, red_flags, red_flag_penalty, strengths, weaknesses, "
                "summary, matched_at"
                ") SELECT "
                "id, job_description_id, candidate_id, resume_id, candidate_name, "
                "filename, rank, final_score, component_scores, matching_skills, "
                "missing_skills, red_flags, red_flag_penalty, strengths, weaknesses, "
                "summary, matched_at FROM match_results"
            )
        )
    else:
        connection.execute(
            sa.text(
                "INSERT INTO match_results_new ("
                "id, job_description_id, candidate_id, resume_id, candidate_name, "
                "filename, rank, final_score, component_scores, matching_skills, "
                "missing_skills, red_flags, red_flag_penalty, strengths, weaknesses, "
                "summary, matched_at"
                ") SELECT "
                "id, 1, candidate_id, resume_id, candidate_name, "
                "filename, rank, final_score, component_scores, matching_skills, "
                "missing_skills, red_flags, red_flag_penalty, strengths, weaknesses, "
                "summary, matched_at FROM match_results"
            )
        )

    connection.execute(sa.text("DROP TABLE match_results"))
    connection.execute(sa.text("ALTER TABLE match_results_new RENAME TO match_results"))
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_match_results_job_description_id "
            "ON match_results (job_description_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_match_results_candidate_id "
            "ON match_results (candidate_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_match_results_resume_id "
            "ON match_results (resume_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_match_results_rank "
            "ON match_results (rank)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_match_results_job_candidate "
            "ON match_results (job_description_id, candidate_id)"
        )
    )
    _drop_legacy_resume_unique_index(connection)


def _migrate_candidates_and_uploads(connection) -> None:
    """Add candidate-centric tables/columns and backfill legacy resume rows."""
    import json

    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if "resumes" in tables:
        columns = {col["name"] for col in inspector.get_columns("resumes")}
        if "candidate_id" not in columns:
            connection.execute(
                sa.text("ALTER TABLE resumes ADD COLUMN candidate_id INTEGER")
            )
        if "is_default" not in columns:
            connection.execute(
                sa.text(
                    "ALTER TABLE resumes ADD COLUMN is_default BOOLEAN "
                    "NOT NULL DEFAULT 1"
                )
            )
        if "extraction_source" not in columns:
            connection.execute(
                sa.text("ALTER TABLE resumes ADD COLUMN extraction_source VARCHAR(32)")
            )
        connection.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_resumes_candidate_id "
                "ON resumes (candidate_id)"
            )
        )

    if "match_results" in tables:
        columns = {col["name"] for col in inspector.get_columns("match_results")}
        if "candidate_id" not in columns:
            connection.execute(
                sa.text("ALTER TABLE match_results ADD COLUMN candidate_id INTEGER")
            )
        connection.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_match_results_candidate_id "
                "ON match_results (candidate_id)"
            )
        )

    if "candidates" not in tables:
        connection.execute(
            sa.text(
                "CREATE TABLE candidates ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "first_name VARCHAR(128), "
                "last_name VARCHAR(128), "
                "email VARCHAR(320) NOT NULL UNIQUE, "
                "phone VARCHAR(64), "
                "linkedin_url VARCHAR(512), "
                "current_location VARCHAR(256), "
                "country VARCHAR(128), "
                "title VARCHAR(256), "
                "passport_number VARCHAR(64), "
                "extracted_data JSON NOT NULL DEFAULT '{}', "
                "calculated_metrics JSON NOT NULL DEFAULT '{}', "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
            )
        )
        connection.execute(
            sa.text("CREATE INDEX IF NOT EXISTS ix_candidates_email ON candidates (email)")
        )
        connection.execute(
            sa.text("CREATE INDEX IF NOT EXISTS ix_candidates_phone ON candidates (phone)")
        )

    if "duplicate_check_settings" not in tables:
        connection.execute(
            sa.text(
                "CREATE TABLE duplicate_check_settings ("
                "id INTEGER PRIMARY KEY, "
                "primary_fields JSON NOT NULL, "
                "secondary_fields JSON NOT NULL, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO duplicate_check_settings "
                "(id, primary_fields, secondary_fields) "
                "VALUES (1, '[\"email\", \"phone\", \"linkedin_url\"]', "
                "'[\"passport_number\"]')"
            )
        )

    if "upload_batches" not in tables:
        connection.execute(
            sa.text(
                "CREATE TABLE upload_batches ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "mode VARCHAR(16) NOT NULL DEFAULT 'bulk', "
                "duplicate_policy VARCHAR(32), "
                "status VARCHAR(32) NOT NULL DEFAULT 'pending', "
                "total_files INTEGER NOT NULL DEFAULT 0, "
                "processed INTEGER NOT NULL DEFAULT 0, "
                "succeeded INTEGER NOT NULL DEFAULT 0, "
                "failed INTEGER NOT NULL DEFAULT 0, "
                "ignored INTEGER NOT NULL DEFAULT 0, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
            )
        )

    if "upload_batch_items" not in tables:
        connection.execute(
            sa.text(
                "CREATE TABLE upload_batch_items ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "batch_id INTEGER NOT NULL, "
                "filename VARCHAR(512) NOT NULL, "
                "file_hash VARCHAR(64), "
                "scan_status VARCHAR(16), "
                "process_status VARCHAR(16), "
                "message TEXT, "
                "candidate_id INTEGER, "
                "resume_id INTEGER, "
                "FOREIGN KEY(batch_id) REFERENCES upload_batches(id) ON DELETE CASCADE)"
            )
        )
        connection.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_upload_batch_items_batch_id "
                "ON upload_batch_items (batch_id)"
            )
        )

    # Backfill orphan resumes into candidates
    if "resumes" in tables and "candidates" in tables:
        orphan_rows = connection.execute(
            sa.text(
                "SELECT id, filename, extracted_data, calculated_metrics, "
                "candidate_email FROM resumes WHERE candidate_id IS NULL"
            )
        ).fetchall()

        for row in orphan_rows:
            resume_id, filename, extracted_raw, metrics_raw, stored_email = row
            try:
                extracted = json.loads(extracted_raw) if extracted_raw else {}
            except json.JSONDecodeError:
                extracted = {}
            try:
                metrics = json.loads(metrics_raw) if metrics_raw else {}
            except json.JSONDecodeError:
                metrics = {}

            personal = extracted.get("Personal_Info", {}) or {}
            email = (stored_email or personal.get("Email") or "").strip().lower()
            if not email or "@" not in email:
                email = f"import-{resume_id}@orphan.local"

            existing = connection.execute(
                sa.text("SELECT id FROM candidates WHERE email = :email"),
                {"email": email},
            ).fetchone()

            if existing:
                candidate_id = existing[0]
            else:
                full_name = (personal.get("Name") or "").strip()
                parts = full_name.split() if full_name else []
                first_name = parts[0] if parts else None
                last_name = " ".join(parts[1:]) if len(parts) > 1 else None
                connection.execute(
                    sa.text(
                        "INSERT INTO candidates ("
                        "first_name, last_name, email, phone, title, "
                        "current_location, extracted_data, calculated_metrics"
                        ") VALUES ("
                        ":first_name, :last_name, :email, :phone, :title, "
                        ":location, :extracted, :metrics)"
                    ),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "phone": personal.get("Phone"),
                        "title": personal.get("Current Designation"),
                        "location": personal.get("Location"),
                        "extracted": json.dumps(extracted),
                        "metrics": json.dumps(metrics),
                    },
                )
                candidate_id = connection.execute(sa.text("SELECT last_insert_rowid()")).scalar()

            connection.execute(
                sa.text(
                    "UPDATE resumes SET candidate_id = :cid, is_default = 1 "
                    "WHERE id = :rid"
                ),
                {"cid": candidate_id, "rid": resume_id},
            )
            connection.execute(
                sa.text(
                    "UPDATE match_results SET candidate_id = :cid "
                    "WHERE resume_id = :rid AND candidate_id IS NULL"
                ),
                {"cid": candidate_id, "rid": resume_id},
            )


def _migrate_upload_metrics(connection) -> None:
    """Add extraction timing and token columns to upload history items."""
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "upload_batch_items" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("upload_batch_items")}
    additions = {
        "duration_ms": "INTEGER",
        "input_tokens": "INTEGER",
        "output_tokens": "INTEGER",
        "total_tokens": "INTEGER",
    }
    for name, col_type in additions.items():
        if name not in columns:
            connection.execute(
                sa.text(f"ALTER TABLE upload_batch_items ADD COLUMN {name} {col_type}")
            )

    extra = {
        "llm_model": "VARCHAR(256)",
        "estimated_cost_usd": "REAL",
        "estimated_cost_credits": "REAL",
    }
    for name, col_type in extra.items():
        if name not in columns:
            connection.execute(
                sa.text(f"ALTER TABLE upload_batch_items ADD COLUMN {name} {col_type}")
            )


def _migrate_model_pricing_settings(connection) -> None:
    import json

    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    if "model_pricing_settings" in inspector.get_table_names():
        return

    from model_pricing_service import DEFAULT_MODEL_PRICING

    connection.execute(
        sa.text(
            "CREATE TABLE model_pricing_settings ("
            "id INTEGER PRIMARY KEY, "
            "cost_display_mode VARCHAR(16) NOT NULL DEFAULT 'usd', "
            "credits_per_usd REAL NOT NULL DEFAULT 1000.0, "
            "model_pricing JSON NOT NULL, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO model_pricing_settings (id, cost_display_mode, credits_per_usd, model_pricing) "
            "VALUES (1, 'usd', 1000.0, :pricing)"
        ),
        {"pricing": json.dumps(DEFAULT_MODEL_PRICING)},
    )


async def init_db() -> None:
    """Create tables on application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_app_settings)
        await conn.run_sync(_migrate_resumes)
        await conn.run_sync(_migrate_job_and_matching)
        await conn.run_sync(_migrate_multi_job_descriptions)
        await conn.run_sync(_migrate_match_results_per_job_unique)
        await conn.run_sync(_migrate_candidates_and_uploads)
        await conn.run_sync(_migrate_upload_metrics)
        await conn.run_sync(_migrate_model_pricing_settings)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
