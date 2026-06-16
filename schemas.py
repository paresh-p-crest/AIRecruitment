"""Pydantic V2 schemas for API requests/responses and LLM structured extraction."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from coercion import coerce_list, coerce_str_list, normalize_personal_info, normalize_skills


class PersonalInfo(BaseModel):
    name: str | None = Field(default=None, alias="Name")
    email: str | None = Field(default=None, alias="Email")
    phone: str | None = Field(default=None, alias="Phone")
    location: str | None = Field(default=None, alias="Location")
    current_company: str | None = Field(default=None, alias="Current Company")
    current_designation: str | None = Field(
        default=None, alias="Current Designation"
    )

    model_config = {"populate_by_name": True}


class ProfessionalExperienceEntry(BaseModel):
    company_name: str | None = Field(default=None, alias="Company Name")
    job_title: str | None = Field(default=None, alias="Job Title")
    employment_type: str | None = Field(
        default=None, alias="Employment Type", description="e.g. Full-time, Contract"
    )
    start_date: str | None = Field(
        default=None, alias="Start Date", description="Start date as written on resume"
    )
    end_date: str | None = Field(
        default=None,
        alias="End Date",
        description="End date or 'Present' / 'Current'",
    )
    responsibilities: list[str] = Field(
        default_factory=list, alias="Responsibilities"
    )
    technologies_used: list[str] = Field(
        default_factory=list, alias="Technologies Used"
    )

    @field_validator("responsibilities", "technologies_used", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        return coerce_str_list(value)

    model_config = {"populate_by_name": True}


class EducationEntry(BaseModel):
    degree: str | None = Field(default=None, alias="Degree")
    specialisation: str | None = Field(default=None, alias="Specialisation")
    college: str | None = Field(default=None, alias="College")
    start_year: str | None = Field(default=None, alias="Start Year")
    end_year: str | None = Field(default=None, alias="End Year")
    grade_cgpa: str | None = Field(default=None, alias="Grade/CGPA")

    model_config = {"populate_by_name": True}


class Skills(BaseModel):
    technical_skills: list[str] = Field(
        default_factory=list, alias="Technical Skills"
    )
    soft_skills: list[str] = Field(default_factory=list, alias="Soft Skills")

    model_config = {"populate_by_name": True}


class CalculatedMetrics(BaseModel):
    total_years_of_experience: float = Field(
        default=0.0, alias="Total_Years_Of_Experience"
    )

    model_config = {"populate_by_name": True}


class ExtractedResume(BaseModel):
    """Structured resume data returned by the LLM extraction node."""

    personal_info: PersonalInfo = Field(default_factory=PersonalInfo, alias="Personal_Info")
    professional_experience: list[ProfessionalExperienceEntry] = Field(
        default_factory=list, alias="Professional_Experience"
    )
    education: list[EducationEntry] = Field(default_factory=list, alias="Education")
    skills: Skills = Field(default_factory=Skills, alias="Skills")

    @field_validator("personal_info", mode="before")
    @classmethod
    def coerce_personal_info(cls, value: Any) -> dict:
        return normalize_personal_info(value)

    @field_validator("professional_experience", "education", mode="before")
    @classmethod
    def coerce_object_lists(cls, value: Any) -> list:
        return coerce_list(value)

    @field_validator("skills", mode="before")
    @classmethod
    def coerce_skills_block(cls, value: Any) -> dict:
        return normalize_skills(value)

    model_config = {"populate_by_name": True}


class ProfileExtraction(BaseModel):
    """Partial extraction: identity, education, and skills (chunked pass 1)."""

    personal_info: PersonalInfo = Field(default_factory=PersonalInfo, alias="Personal_Info")
    education: list[EducationEntry] = Field(default_factory=list, alias="Education")
    skills: Skills = Field(default_factory=Skills, alias="Skills")

    @field_validator("personal_info", mode="before")
    @classmethod
    def coerce_personal_info(cls, value: Any) -> dict:
        return normalize_personal_info(value)

    @field_validator("education", mode="before")
    @classmethod
    def coerce_object_lists(cls, value: Any) -> list:
        return coerce_list(value)

    @field_validator("skills", mode="before")
    @classmethod
    def coerce_skills_block(cls, value: Any) -> dict:
        return normalize_skills(value)

    model_config = {"populate_by_name": True}


class ExperienceExtraction(BaseModel):
    """Partial extraction: work history only (chunked pass 2+)."""

    professional_experience: list[ProfessionalExperienceEntry] = Field(
        default_factory=list, alias="Professional_Experience"
    )

    @field_validator("professional_experience", mode="before")
    @classmethod
    def coerce_object_lists(cls, value: Any) -> list:
        return coerce_list(value)

    model_config = {"populate_by_name": True}


class DashboardTopMatch(BaseModel):
    resume_id: int
    candidate_name: str | None = None
    filename: str | None = None
    final_score: float
    rank: int | None = None


class DashboardSnapshot(BaseModel):
    total_candidates: int = 0
    matched_candidates: int = 0
    unmatched_candidates: int = 0
    avg_match_score: float | None = None
    avg_years_experience: float | None = None
    job_description_valid: bool = False
    job_description_has_content: bool = False
    active_job_id: int | None = None
    active_job_title: str | None = None
    job_posting_count: int = 0
    file_types: dict[str, int] = Field(default_factory=dict)
    top_matches: list[DashboardTopMatch] = Field(default_factory=list)
    doc_extraction_backends: dict[str, bool] = Field(default_factory=dict)
    extraction_chunking_enabled: bool = True
    extraction_chunk_threshold: int = 9000
    archive_doc_files: int | None = None


class ResumeUploadResponse(BaseModel):
    id: int
    filename: str
    raw_text: str
    extracted_data: dict[str, Any]
    calculated_metrics: dict[str, Any]
    created_at: datetime


class ResumeUploadItemResult(BaseModel):
    filename: str
    status: Literal["success", "skipped", "error"]
    message: str | None = None
    skip_reason: Literal["duplicate_file", "duplicate_email"] | None = None
    duplicate_of_id: int | None = None
    resume: ResumeUploadResponse | None = None


class BulkResumeUploadResponse(BaseModel):
    total: int
    succeeded: int
    skipped: int
    failed: int
    results: list[ResumeUploadItemResult]


class ResumeListItem(BaseModel):
    id: int
    candidate_id: int
    resume_id: int | None = None
    filename: str
    candidate_name: str | None
    candidate_email: str | None
    total_years_of_experience: float | None
    match_score: float | None = None
    match_rank: int | None = None
    has_resume: bool = True
    created_at: datetime


class ResetDataResponse(BaseModel):
    candidates: int
    resumes: int
    match_results: int
    upload_batches: int
    upload_batch_items: int


class JobDescriptionPublic(BaseModel):
    id: int
    title: str
    raw_text: str
    parsed: dict[str, Any]
    is_active: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    has_content: bool = False
    is_valid_for_matching: bool = False
    match_count: int = 0


class JobDescriptionListItem(BaseModel):
    id: int
    title: str
    is_active: bool = False
    is_valid_for_matching: bool = False
    match_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobDescriptionUpdate(BaseModel):
    raw_text: str = Field(default="", description="Full job description text (may be empty)")
    title: str | None = Field(default=None, description="Optional display title for this role")


class JobDescriptionCreate(BaseModel):
    raw_text: str = Field(default="", description="Full job description text")
    title: str | None = Field(default=None, description="Optional display title")
    set_as_active: bool = Field(
        default=True,
        description="When true, this job becomes the active posting for matching",
    )


class ComponentScoreBreakdown(BaseModel):
    key: str
    label: str
    weight_percent: float
    score: float
    weighted_points: float


class JobDescriptionDeleteResponse(BaseModel):
    deleted_job_id: int
    deleted_title: str
    matches_removed: int
    candidates_preserved: bool = True
    new_active_job_id: int | None = None


class MatchResultDetail(BaseModel):
    resume_id: int
    job_description_id: int | None = None
    job_title: str | None = None
    candidate_name: str | None = None
    filename: str | None = None
    rank: int | None = None
    final_score: float
    subtotal_score: float
    component_scores: dict[str, float]
    component_breakdown: list[ComponentScoreBreakdown]
    matching_skills: list[str]
    missing_skills: list[str]
    red_flags: list[dict[str, Any]]
    red_flag_penalty: float
    strengths: list[str]
    weaknesses: list[str]
    summary: str
    matched_at: datetime


class MatchRunResponse(BaseModel):
    job_description_id: int | None = None
    job_title: str | None = None
    total: int
    results: list[MatchResultDetail]
    matched_new: int = 0
    skipped_existing: int = 0


class SettingsPublic(BaseModel):
    llm_provider: Literal["aws_bedrock", "openai", "google"]
    aws_access_key_id: str | None = None
    aws_secret_access_key_masked: str | None = None
    aws_session_token_masked: str | None = None
    aws_secret_configured: bool = False
    aws_session_token_configured: bool = False
    aws_region: str = "us-east-1"
    bedrock_model_id: str
    openai_api_key_masked: str | None = None
    openai_api_key_configured: bool = False
    openai_model: str = "gpt-4o-mini"
    google_api_key_masked: str | None = None
    google_api_key_configured: bool = False
    google_model: str = "gemini-2.5-flash"
    updated_at: datetime | None = None


class SettingsUpdate(BaseModel):
    llm_provider: Literal["aws_bedrock", "openai", "google"] = "aws_bedrock"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = Field(
        default=None,
        description="Leave empty to keep the existing secret.",
    )
    aws_session_token: str | None = Field(
        default=None,
        description="Optional session token for sandbox/temporary AWS credentials.",
    )
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    openai_api_key: str | None = Field(
        default=None,
        description="Leave empty to keep the existing API key.",
    )
    openai_model: str = "gpt-4o-mini"
    google_api_key: str | None = Field(
        default=None,
        description="Leave empty to keep the existing Google AI Studio API key.",
    )
    google_model: str = "gemini-2.5-flash"


class SettingsTestRequest(BaseModel):
    """Test a provider tab using form values merged with saved credentials."""

    llm_provider: Literal["aws_bedrock", "openai", "google"]
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    google_api_key: str | None = None
    google_model: str = "gemini-2.5-flash"


class SettingsTestResponse(BaseModel):
    success: bool
    provider: str
    model: str
    message: str


DuplicatePolicy = Literal["ignore", "add_as_default", "add_as_new_resume"]


class PrescanFileResult(BaseModel):
    filename: str
    file_hash: str
    status: Literal["ok", "warning", "error"]
    emails_found: list[str] = Field(default_factory=list)
    phones_found: list[str] = Field(default_factory=list)
    linkedin_urls_found: list[str] = Field(default_factory=list)
    message: str | None = None
    duplicate_of_filename: str | None = None
    duplicate_in_database: bool = False
    skipped_ai: bool = True
    processable: bool = False


class PrescanResponse(BaseModel):
    total: int
    ready: int
    warnings: int
    errors: int
    can_proceed: bool
    ai_calls_avoided: int = 0
    estimated_tokens_saved: int = 0
    results: list[PrescanFileResult]


class CandidateProcessResult(BaseModel):
    filename: str
    status: Literal["success", "ignored", "error", "duplicate_review"]
    message: str | None = None
    candidate_id: int | None = None
    resume_id: int | None = None
    is_default: bool | None = None
    extraction_source: str | None = None
    existing_candidate_id: int | None = None
    parsed_preview: dict[str, Any] | None = None
    existing_snapshot: dict[str, Any] | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    llm_model: str | None = None
    estimated_cost_usd: float | None = None
    estimated_cost_credits: float | None = None


class UploadHistoryClearResponse(BaseModel):
    deleted_items: int


class UploadHistoryItem(BaseModel):
    id: int
    batch_id: int
    mode: str
    filename: str
    process_status: str | None = None
    message: str | None = None
    candidate_id: int | None = None
    resume_id: int | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    llm_model: str | None = None
    estimated_cost_usd: float | None = None
    estimated_cost_credits: float | None = None
    created_at: datetime


class BulkCandidateUploadResponse(BaseModel):
    batch_id: int
    total: int
    succeeded: int
    ignored: int
    failed: int
    results: list[CandidateProcessResult]


class SingleUploadConfirm(BaseModel):
    duplicate_policy: DuplicatePolicy


class CandidateListItem(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    email: str
    phone: str | None = None
    title: str | None = None
    total_years_of_experience: float | None = None
    default_resume_id: int | None = None
    resume_count: int = 0
    match_score: float | None = None
    match_rank: int | None = None
    created_at: datetime
    updated_at: datetime


class CandidateDetail(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    email: str
    phone: str | None = None
    linkedin_url: str | None = None
    current_location: str | None = None
    country: str | None = None
    title: str | None = None
    passport_number: str | None = None
    extracted_data: dict[str, Any]
    calculated_metrics: dict[str, Any]
    default_resume_id: int | None = None
    resumes: list[ResumeUploadResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CandidateProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    current_location: str | None = None
    country: str | None = None
    title: str | None = None
    passport_number: str | None = None


class DuplicateFieldWarning(BaseModel):
    field: str
    label: str
    message: str
    conflicting_candidate_id: int
    conflicting_candidate_name: str | None = None
    conflicting_candidate_email: str | None = None


class CandidateProfileUpdateResponse(BaseModel):
    saved: bool = True
    duplicate_warnings: list[DuplicateFieldWarning] = Field(default_factory=list)
    candidate: CandidateDetail


class DuplicateCheckSettingsPublic(BaseModel):
    primary_fields: list[str]
    secondary_fields: list[str]
    updated_at: datetime | None = None


class DuplicateCheckSettingsUpdate(BaseModel):
    primary_fields: list[str] = Field(
        default_factory=lambda: ["email", "phone", "linkedin_url"]
    )
    secondary_fields: list[str] = Field(default_factory=lambda: ["passport_number"])


class ModelPricingEntry(BaseModel):
    model_id: str
    provider: str = ""
    label: str = ""
    input_per_million_usd: float = 0.0
    output_per_million_usd: float = 0.0


class ModelPricingSettingsPublic(BaseModel):
    cost_display_mode: Literal["usd", "credits"] = "usd"
    credits_per_usd: float = 1000.0
    model_pricing: list[ModelPricingEntry] = Field(default_factory=list)
    updated_at: datetime | None = None


class ModelPricingSettingsUpdate(BaseModel):
    cost_display_mode: Literal["usd", "credits"] = "usd"
    credits_per_usd: float = Field(default=1000.0, ge=0.01)
    model_pricing: list[ModelPricingEntry] = Field(default_factory=list)


class SearchContextMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class CandidateSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=15, ge=1, le=50)
    context: list[SearchContextMessage] = Field(default_factory=list)
    previous_result_ids: list[int] = Field(default_factory=list)


class CandidateSearchResultItem(BaseModel):
    candidate_id: int
    resume_id: int | None = None
    name: str
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    match_reason: str | None = None
    relevance_score: float | int | None = None


class CandidateSearchResponse(BaseModel):
    query: str
    summary: str
    results: list[CandidateSearchResultItem] = Field(default_factory=list)
