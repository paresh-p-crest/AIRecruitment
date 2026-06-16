"""SQLAlchemy ORM models for persisted resume records."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Candidate(Base):
    """Canonical candidate profile — parsed data lives here (per-candidate storage)."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    passport_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    calculated_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    resumes: Mapped[list["ResumeRecord"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class ResumeRecord(Base):
    """Resume file attachment — raw text + link to candidate profile."""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extraction_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Legacy columns kept for migration / backward-compatible reads
    candidate_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    extracted_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    calculated_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate | None"] = relationship(back_populates="resumes")
    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class DuplicateCheckSettings(Base):
    """Singleton admin config for duplicate detection fields."""

    __tablename__ = "duplicate_check_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    primary_fields: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["email", "phone", "linkedin_url"],
    )
    secondary_fields: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["passport_number"]
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UploadBatch(Base):
    """Tracks a bulk or single upload session."""

    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="bulk")
    duplicate_policy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ignored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["UploadBatchItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class UploadBatchItem(Base):
    __tablename__ = "upload_batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scan_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    process_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resume_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost_credits: Mapped[float | None] = mapped_column(Float, nullable=True)

    batch: Mapped["UploadBatch"] = relationship(back_populates="items")


class JobDescription(Base):
    """Job posting / requisition — multiple rows; one active for new matching."""

    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    match_results: Mapped[list["MatchResult"]] = relationship(
        back_populates="job_description", cascade="all, delete-orphan"
    )


class MatchResult(Base):
    """Hybrid match score for a candidate against a specific job description."""

    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint(
            "job_description_id",
            "candidate_id",
            name="uq_match_results_job_candidate",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_description_id: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True, index=True
    )
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    candidate_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    component_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    matching_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    red_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    red_flag_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate | None"] = relationship(back_populates="match_results")
    resume: Mapped["ResumeRecord | None"] = relationship(back_populates="match_results")
    job_description: Mapped["JobDescription"] = relationship(back_populates="match_results")


class AppSettings(Base):
    """Singleton row (id=1) for LLM provider and API credentials."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    llm_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="aws_bedrock"
    )
    aws_access_key_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    aws_secret_access_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    aws_session_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    aws_region: Mapped[str] = mapped_column(
        String(32), nullable=False, default="us-east-1"
    )
    bedrock_model_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="anthropic.claude-3-sonnet-20240229-v1:0",
    )
    openai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    openai_model: Mapped[str] = mapped_column(
        String(64), nullable=False, default="gpt-4o-mini"
    )
    google_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_model: Mapped[str] = mapped_column(
        String(64), nullable=False, default="gemini-2.5-flash"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelPricingSettings(Base):
    """Singleton pricing config for LLM token cost estimates."""

    __tablename__ = "model_pricing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cost_display_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="usd"
    )
    credits_per_usd: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    model_pricing: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
