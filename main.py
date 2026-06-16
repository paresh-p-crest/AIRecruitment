"""
AI Recruitment Assistant Platform — FastAPI backend (Phase 1 & 2).

Run locally:
    1. Create and activate a virtual environment
    2. pip install -r requirements.txt
    3. Copy .env.example to .env (optional — credentials can be set via Settings UI)
    4. uvicorn main:app --reload --host 0.0.0.0 --port 8000

Configure LLM credentials:
    - Open the Settings page in the UI (http://localhost:3000/settings), or
    - Use GET/PUT /api/v1/settings API endpoints, or
    - Set AWS / OpenAI keys in .env as fallback defaults
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, get_db, init_db
from llm_factory import build_llm_from_settings
from jd_service import (
    SAMPLE_JOB_DESCRIPTION,
    activate_job_description,
    create_job_description,
    delete_job_description,
    ensure_job_description_row,
    get_job_description,
    list_job_descriptions,
    update_job_description,
)
from matching_service import (
    get_match_for_resume,
    get_match_results,
    run_matching,
    run_matching_for_resume,
)
from dashboard_service import get_dashboard_snapshot
from candidate_service import (
    confirm_single_upload,
    delete_by_resume_id,
    delete_candidate,
    ensure_duplicate_settings,
    get_candidate_detail,
    get_duplicate_settings_public,
    list_candidates,
    clear_upload_history,
    delete_upload_history_item,
    list_upload_history,
    process_uploaded_file,
    purge_orphan_candidates,
    reset_all_candidate_data,
    run_bulk_process,
    run_prescan,
    update_candidate_profile,
    update_duplicate_settings,
)
from models import Candidate, MatchResult, ResumeRecord
from prescan_service import MAX_BULK_FILES
from resume_service import (
    process_resume_bytes,
    record_to_response,
)
from schemas import (
    BulkCandidateUploadResponse,
    BulkResumeUploadResponse,
    CandidateDetail,
    CandidateSearchRequest,
    CandidateSearchResponse,
    DashboardSnapshot,
    CandidateListItem,
    CandidateProcessResult,
    UploadHistoryClearResponse,
    UploadHistoryItem,
    CandidateProfileUpdate,
    CandidateProfileUpdateResponse,
    DuplicateCheckSettingsPublic,
    DuplicateCheckSettingsUpdate,
    DuplicatePolicy,
    JobDescriptionCreate,
    JobDescriptionDeleteResponse,
    JobDescriptionListItem,
    JobDescriptionPublic,
    JobDescriptionUpdate,
    MatchResultDetail,
    MatchRunResponse,
    ModelPricingSettingsPublic,
    ModelPricingSettingsUpdate,
    PrescanResponse,
    ResetDataResponse,
    ResumeListItem,
    ResumeUploadItemResult,
    ResumeUploadResponse,
    SettingsPublic,
    SettingsTestRequest,
    SettingsTestResponse,
    SettingsUpdate,
)
from model_pricing_service import (
    ensure_pricing_settings,
    get_pricing_public,
    update_pricing_settings,
)
from search_service import search_candidates
from settings_service import (
    ensure_settings_row,
    get_public_settings,
    update_settings,
)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as session:
        await ensure_settings_row(session)
        await ensure_job_description_row(session)
        await ensure_duplicate_settings(session)
        await ensure_pricing_settings(session)
        await purge_orphan_candidates(session)
        await session.commit()
    yield


app = FastAPI(
    title="AI Recruitment Assistant Platform",
    description="Phase 1 (Resume Upload) and Phase 2 (Data Extraction) demo API",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    from doc_converter import can_extract_doc, get_doc_extraction_capabilities
    from utils import ALLOWED_EXTENSIONS, PDF_EXTRACTORS

    doc_caps = get_doc_extraction_capabilities()
    return {
        "status": "ok",
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "pdf_extractors": PDF_EXTRACTORS,
        "doc_extraction": doc_caps,
        "doc_extraction_available": can_extract_doc(),
        "libreoffice_available": doc_caps.get("libreoffice", False),
        "textract_pdf_only": True,
    }


@app.get(
    "/api/v1/dashboard",
    response_model=DashboardSnapshot,
    summary="Pipeline snapshot: candidates, matches, JD readiness, parsing health",
)
async def read_dashboard(db: AsyncSession = Depends(get_db)):
    return await get_dashboard_snapshot(db)


@app.get(
    "/api/v1/settings",
    response_model=SettingsPublic,
    summary="Get current LLM provider settings (secrets masked)",
)
async def read_settings(db: AsyncSession = Depends(get_db)):
    return await get_public_settings(db)


@app.put(
    "/api/v1/settings",
    response_model=SettingsPublic,
    summary="Update LLM provider and API credentials",
)
async def save_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_settings(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/v1/settings/test",
    response_model=SettingsTestResponse,
    summary="Test an LLM provider tab (active tab) without switching the in-use provider",
)
async def test_settings(
    payload: SettingsTestRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    from settings_service import (
        get_active_model_name,
        get_effective_settings,
        merge_settings_for_test,
        validate_provider_config,
    )

    saved = await get_effective_settings(db)
    settings = merge_settings_for_test(saved, payload) if payload else saved
    model = get_active_model_name(settings)
    try:
        validate_provider_config(settings)
        llm = build_llm_from_settings(settings)
        response = await llm.ainvoke("Reply with exactly: OK")
        content = getattr(response, "content", str(response))
        return SettingsTestResponse(
            success=True,
            provider=settings.llm_provider,
            model=model,
            message=f"Connection successful. Model responded: {content!s}"[:500],
        )
    except Exception as exc:
        return SettingsTestResponse(
            success=False,
            provider=settings.llm_provider,
            model=model,
            message=str(exc)[:500],
        )


async def _read_upload_files(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one resume file is required.",
        )
    if len(files) > MAX_BULK_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A maximum of {MAX_BULK_FILES} files can be uploaded at once.",
        )
    payload: list[tuple[str, bytes]] = []
    for upload in files:
        payload.append((upload.filename or "unknown", await upload.read()))
    return payload


@app.post(
    "/api/v1/candidates/upload/scan",
    response_model=PrescanResponse,
    summary="Pre-scan resumes before AI extraction (hash, email, duplicates)",
)
async def scan_candidate_uploads(
    files: list[UploadFile] = File(..., description="Up to 50 resume files"),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await _read_upload_files(files)
        return await run_prescan(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/v1/candidates/upload/bulk",
    response_model=BulkCandidateUploadResponse,
    summary="Process bulk upload after scan with a global duplicate policy",
)
async def bulk_upload_candidates(
    duplicate_policy: DuplicatePolicy,
    files: list[UploadFile] = File(..., description="Resume files to process"),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await _read_upload_files(files)
        report = await run_prescan(db, payload)
        if not report["can_proceed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pre-scan has blocking errors. Fix files and scan again.",
            )
        result = await run_bulk_process(db, payload, duplicate_policy)
        return BulkCandidateUploadResponse(
            batch_id=result["batch_id"],
            total=result["total"],
            succeeded=result["succeeded"],
            ignored=result["ignored"],
            failed=result["failed"],
            results=[CandidateProcessResult(**item) for item in result["results"]],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.get(
    "/api/v1/candidates/upload/history",
    response_model=list[UploadHistoryItem],
    summary="Recent upload and extraction history with timing and token usage",
)
async def read_upload_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    capped = max(1, min(limit, 200))
    rows = await list_upload_history(db, limit=capped)
    return [UploadHistoryItem(**row) for row in rows]


@app.delete(
    "/api/v1/candidates/upload/history",
    response_model=UploadHistoryClearResponse,
    summary="Clear all upload history entries",
)
async def clear_upload_history_entries(db: AsyncSession = Depends(get_db)):
    deleted = await clear_upload_history(db)
    return UploadHistoryClearResponse(deleted_items=deleted)


@app.delete(
    "/api/v1/candidates/upload/history/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one upload history entry",
)
async def delete_upload_history_entry(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_upload_history_item(db, item_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/v1/candidates/upload/single",
    response_model=CandidateProcessResult,
    summary="Upload one resume; returns duplicate comparison when needed",
)
async def single_upload_candidate(
    file: UploadFile = File(..., description="PDF, DOCX, or DOC resume file"),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    filename = file.filename or "unknown"
    try:
        outcome = await process_uploaded_file(
            db,
            filename,
            content,
            allow_duplicate_review=True,
        )
        return CandidateProcessResult(**outcome)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/v1/candidates/upload/single/confirm",
    response_model=CandidateProcessResult,
    summary="Confirm single upload after duplicate review",
)
async def confirm_single_upload_candidate(
    duplicate_policy: DuplicatePolicy,
    file: UploadFile = File(..., description="Same resume file as initial upload"),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    filename = file.filename or "unknown"
    try:
        outcome = await confirm_single_upload(
            db, filename, content, duplicate_policy
        )
        return CandidateProcessResult(**outcome)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@app.get(
    "/api/v1/candidates",
    response_model=list[CandidateListItem],
    summary="List all candidates",
)
async def list_all_candidates(db: AsyncSession = Depends(get_db)):
    rows = await list_candidates(db)
    return [CandidateListItem(**row) for row in rows]


@app.delete(
    "/api/v1/candidates/reset",
    response_model=ResetDataResponse,
    summary="Delete all candidates, resumes, and match results",
)
async def reset_all_candidates(
    confirm: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass confirm=true to permanently delete all candidate data.",
        )
    return await reset_all_candidate_data(db)


@app.get(
    "/api/v1/candidates/{candidate_id}",
    response_model=CandidateDetail,
    summary="Get candidate profile and resume attachments",
)
async def get_candidate(candidate_id: int, db: AsyncSession = Depends(get_db)):
    detail = await get_candidate_detail(db, candidate_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found.",
        )
    return CandidateDetail(**detail)


@app.patch(
    "/api/v1/candidates/{candidate_id}",
    response_model=CandidateProfileUpdateResponse,
    summary="Update editable candidate identity fields",
)
async def patch_candidate_profile(
    candidate_id: int,
    body: CandidateProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    detail, warnings = await update_candidate_profile(
        db,
        candidate_id,
        body.model_dump(exclude_unset=True),
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found.",
        )
    await db.commit()
    return CandidateProfileUpdateResponse(
        saved=True,
        duplicate_warnings=warnings,
        candidate=CandidateDetail(**detail),
    )


@app.delete(
    "/api/v1/candidates/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a candidate and all attached resumes",
)
async def remove_candidate(candidate_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await delete_candidate(db, candidate_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found.",
        )


@app.get(
    "/api/v1/settings/duplicate-check",
    response_model=DuplicateCheckSettingsPublic,
    summary="Get duplicate detection field configuration",
)
async def read_duplicate_check_settings(db: AsyncSession = Depends(get_db)):
    return await get_duplicate_settings_public(db)


@app.put(
    "/api/v1/settings/duplicate-check",
    response_model=DuplicateCheckSettingsPublic,
    summary="Update duplicate detection field configuration",
)
async def save_duplicate_check_settings(
    payload: DuplicateCheckSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_duplicate_settings(
        db, payload.primary_fields, payload.secondary_fields
    )


@app.get(
    "/api/v1/settings/pricing",
    response_model=ModelPricingSettingsPublic,
    summary="Get per-model token pricing and cost display mode",
)
async def read_model_pricing_settings(db: AsyncSession = Depends(get_db)):
    return await get_pricing_public(db)


@app.put(
    "/api/v1/settings/pricing",
    response_model=ModelPricingSettingsPublic,
    summary="Update per-model token pricing and cost display mode",
)
async def save_model_pricing_settings(
    payload: ModelPricingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_pricing_settings(
        db,
        cost_display_mode=payload.cost_display_mode,
        credits_per_usd=payload.credits_per_usd,
        model_pricing=[entry.model_dump() for entry in payload.model_pricing],
    )


@app.post(
    "/api/v1/candidates/search",
    response_model=CandidateSearchResponse,
    summary="Search all candidates with natural language",
)
async def search_all_candidates(
    payload: CandidateSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await search_candidates(
            db,
            payload.query,
            limit=payload.limit,
            context=[m.model_dump() for m in payload.context],
            previous_result_ids=payload.previous_result_ids,
        )
        return CandidateSearchResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _item_result_from_process(result) -> ResumeUploadItemResult:
    return ResumeUploadItemResult(
        filename=result.filename,
        status=result.status,
        message=result.message,
        skip_reason=result.skip_reason,
        duplicate_of_id=result.duplicate_of_id,
        resume=record_to_response(result.resume) if result.resume else None,
    )


@app.post(
    "/api/v1/resumes/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"description": "Duplicate resume skipped"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Parse or extraction error"},
    },
    summary="Upload a single resume and run the extraction pipeline",
)
async def upload_resume(
    file: UploadFile = File(..., description="PDF, DOCX, or DOC resume file"),
    db: AsyncSession = Depends(get_db),
):
    """Accept one resume file; skip duplicates by file hash or candidate email."""
    content = await file.read()
    result = await process_resume_bytes(
        db,
        file.filename or "unknown",
        content,
    )

    if result.status == "skipped":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": result.message,
                "skip_reason": result.skip_reason,
                "duplicate_of_id": result.duplicate_of_id,
            },
        )

    if result.status == "error":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.message or "Upload failed.",
        )

    assert result.resume is not None
    return record_to_response(result.resume)


@app.post(
    "/api/v1/resumes/upload/bulk",
    response_model=BulkResumeUploadResponse,
    summary="Upload multiple resumes with per-file duplicate detection",
)
async def upload_resumes_bulk(
    response: Response,
    files: list[UploadFile] = File(
        ..., description="One or more PDF, DOCX, or DOC resume files"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Process multiple resumes sequentially; duplicates are skipped, not failed."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one resume file is required.",
        )

    if len(files) > MAX_BULK_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A maximum of {MAX_BULK_FILES} files can be uploaded at once.",
        )

    seen_hashes: set[str] = set()
    seen_emails: set[str] = set()
    results: list[ResumeUploadItemResult] = []

    for upload in files:
        content = await upload.read()
        processed = await process_resume_bytes(
            db,
            upload.filename or "unknown",
            content,
            seen_hashes=seen_hashes,
            seen_emails=seen_emails,
        )
        results.append(_item_result_from_process(processed))

    succeeded = sum(1 for item in results if item.status == "success")
    skipped = sum(1 for item in results if item.status == "skipped")
    failed = sum(1 for item in results if item.status == "error")

    response.status_code = (
        status.HTTP_201_CREATED if succeeded else status.HTTP_200_OK
    )
    return BulkResumeUploadResponse(
        total=len(results),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        results=results,
    )


@app.get(
    "/api/v1/job-description",
    response_model=JobDescriptionPublic,
    summary="Get the active job description",
)
async def read_job_description(db: AsyncSession = Depends(get_db)):
    return await get_job_description(db)


@app.get(
    "/api/v1/job-descriptions",
    response_model=list[JobDescriptionListItem],
    summary="List all job postings (active first)",
)
async def read_job_descriptions(db: AsyncSession = Depends(get_db)):
    return await list_job_descriptions(db)


@app.get(
    "/api/v1/job-descriptions/{job_id}",
    response_model=JobDescriptionPublic,
    summary="Get a job description by id",
)
async def read_job_description_by_id(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await get_job_description(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.put(
    "/api/v1/job-description",
    response_model=JobDescriptionPublic,
    summary="Save the active job description",
)
async def save_job_description(
    payload: JobDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_job_description(db, payload)


@app.put(
    "/api/v1/job-descriptions/{job_id}",
    response_model=JobDescriptionPublic,
    summary="Update a specific job description",
)
async def save_job_description_by_id(
    job_id: int,
    payload: JobDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_job_description(db, payload, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post(
    "/api/v1/job-descriptions",
    response_model=JobDescriptionPublic,
    summary="Create a new job posting (optionally set as active)",
)
async def create_job_posting(
    payload: JobDescriptionCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_job_description(db, payload)


@app.post(
    "/api/v1/job-descriptions/{job_id}/activate",
    response_model=JobDescriptionPublic,
    summary="Switch the active job posting used for matching",
)
async def activate_job_posting(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await activate_job_description(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.delete(
    "/api/v1/job-descriptions/{job_id}",
    response_model=JobDescriptionDeleteResponse,
    summary="Delete a job posting and its match results (candidates preserved)",
)
async def remove_job_posting(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await delete_job_description(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.get(
    "/api/v1/job-descriptions/{job_id}/matches",
    response_model=MatchRunResponse,
    summary="Get match results for a specific job posting",
)
async def read_job_match_results(job_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await get_match_results(db, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.get(
    "/api/v1/job-description/sample",
    summary="Get a sample job description template",
)
async def sample_job_description():
    return {"raw_text": SAMPLE_JOB_DESCRIPTION}


@app.post(
    "/api/v1/matching/run",
    response_model=MatchRunResponse,
    summary="Match candidates not yet scored for the selected job",
)
async def execute_matching(
    include_llm: bool = True,
    job_id: int | None = None,
    rematch_all: bool = False,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await run_matching(
            db,
            include_llm=include_llm,
            job_id=job_id,
            rematch_all=rematch_all,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Matching failed: {exc}",
        ) from exc


@app.get(
    "/api/v1/matching/results",
    response_model=MatchRunResponse,
    summary="Get latest match results ranked by score",
)
async def read_match_results(
    job_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_match_results(db, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post(
    "/api/v1/matching/run/{resume_id}",
    response_model=MatchResultDetail,
    summary="Run hybrid matching for a single candidate",
)
async def execute_matching_for_resume(
    resume_id: int,
    include_llm: bool = True,
    job_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await run_matching_for_resume(
            db, resume_id, include_llm=include_llm, job_id=job_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Matching failed: {exc}",
        ) from exc


@app.get(
    "/api/v1/matching/results/{resume_id}",
    response_model=MatchResultDetail,
    summary="Get match analysis for one candidate",
)
async def read_match_result(
    resume_id: int,
    job_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    match = await get_match_for_resume(db, resume_id, job_id=job_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No match results found for this resume. Run matching first.",
        )
    return match


@app.get(
    "/api/v1/resumes",
    response_model=list[ResumeListItem],
    summary="List all parsed candidates",
)
async def list_resumes(
    job_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return all candidates; id is resume id when available, else candidate id."""
    try:
        rows = await list_candidates(db, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    items: list[ResumeListItem] = []
    for row in rows:
        candidate_id = row["id"]
        resume_id = row.get("default_resume_id")
        name_parts = [row.get("first_name"), row.get("last_name")]
        candidate_name = " ".join(p for p in name_parts if p) or None
        list_id = resume_id if resume_id else candidate_id
        items.append(
            ResumeListItem(
                id=list_id,
                candidate_id=candidate_id,
                resume_id=resume_id,
                filename=row.get("default_resume_filename") or "(no resume file)",
                candidate_name=candidate_name,
                candidate_email=row.get("email"),
                total_years_of_experience=row.get("total_years_of_experience"),
                match_score=row.get("match_score"),
                match_rank=row.get("match_rank"),
                has_resume=resume_id is not None,
                created_at=row["created_at"],
            )
        )
    return items


@app.get(
    "/api/v1/resumes/{resume_id}",
    response_model=ResumeUploadResponse,
    summary="Get a single parsed resume by ID",
)
async def get_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    """Return full structured data for one resume (candidate profile when linked)."""
    record = await db.get(ResumeRecord, resume_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with id {resume_id} not found.",
        )

    extracted = record.extracted_data
    metrics = record.calculated_metrics
    if record.candidate_id:
        candidate = await db.get(Candidate, record.candidate_id)
        if candidate:
            extracted = candidate.extracted_data or extracted
            metrics = candidate.calculated_metrics or metrics

    return ResumeUploadResponse(
        id=record.id,
        filename=record.filename,
        raw_text=record.raw_text,
        extracted_data=extracted,
        calculated_metrics=metrics,
        created_at=record.created_at,
    )


@app.delete(
    "/api/v1/resumes/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a parsed resume record",
)
async def delete_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    """Remove resume and parent candidate so duplicates are fully cleared."""
    if await delete_by_resume_id(db, resume_id):
        return
    if await delete_candidate(db, resume_id):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Resume or candidate with id {resume_id} not found.",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
