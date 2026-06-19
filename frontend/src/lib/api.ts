const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ResumeListItem {
  id: number;
  candidate_id: number;
  resume_id: number | null;
  filename: string;
  candidate_name: string | null;
  candidate_email: string | null;
  total_years_of_experience: number | null;
  match_score: number | null;
  match_rank: number | null;
  has_resume: boolean;
  created_at: string;
}

export interface ResumeDetail {
  id: number;
  filename: string;
  raw_text: string;
  extracted_data: ExtractedData;
  calculated_metrics: CalculatedMetrics;
  created_at: string;
}

export interface PersonalInfo {
  Name?: string | null;
  Email?: string | null;
  Phone?: string | null;
  Location?: string | null;
  "Current Company"?: string | null;
  "Current Designation"?: string | null;
}

export interface ProfessionalExperience {
  "Company Name"?: string | null;
  "Job Title"?: string | null;
  "Employment Type"?: string | null;
  "Start Date"?: string | null;
  "End Date"?: string | null;
  Responsibilities?: string[];
  "Technologies Used"?: string[];
}

export interface Education {
  Degree?: string | null;
  Specialisation?: string | null;
  College?: string | null;
  "Start Year"?: string | null;
  "End Year"?: string | null;
  "Grade/CGPA"?: string | null;
}

export interface Skills {
  "Technical Skills"?: string[];
  "Soft Skills"?: string[];
}

export interface ExtractedData {
  Personal_Info: PersonalInfo;
  Professional_Experience: ProfessionalExperience[];
  Education: Education[];
  Skills: Skills;
}

export interface CalculatedMetrics {
  Total_Years_Of_Experience: number;
}

function formatApiError(body: { detail?: unknown }, status: number): string {
  if (!body.detail) {
    return `Request failed (${status})`;
  }
  if (typeof body.detail === "string") {
    return body.detail;
  }
  if (
    typeof body.detail === "object" &&
    body.detail !== null &&
    "message" in body.detail &&
    typeof (body.detail as { message: unknown }).message === "string"
  ) {
    return (body.detail as { message: string }).message;
  }
  return JSON.stringify(body.detail);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = formatApiError(body, response.status);
    } catch {
      // ignore parse errors
    }
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export interface DashboardTopMatch {
  resume_id: number;
  candidate_name: string | null;
  filename: string | null;
  final_score: number;
  rank: number | null;
}

export interface DashboardSkillStat {
  skill: string;
  candidate_count: number;
  percent: number;
}

export interface DashboardSnapshot {
  total_candidates: number;
  matched_candidates: number;
  unmatched_candidates: number;
  avg_match_score: number | null;
  avg_years_experience: number | null;
  has_active_job: boolean;
  job_description_valid: boolean;
  job_description_has_content: boolean;
  active_job_id: number | null;
  active_job_title: string | null;
  job_posting_count: number;
  file_types: Record<string, number>;
  top_matches: DashboardTopMatch[];
  top_skills: DashboardSkillStat[];
  doc_extraction_backends: Record<string, boolean>;
  extraction_chunking_enabled: boolean;
  extraction_chunk_threshold: number;
  archive_doc_files: number | null;
}

export async function getDashboard(): Promise<DashboardSnapshot> {
  const res = await fetch(`${API_URL}/api/v1/dashboard`, { cache: "no-store" });
  return handleResponse<DashboardSnapshot>(res);
}

export async function listResumes(jobId?: number): Promise<ResumeListItem[]> {
  const query = jobId != null ? `?job_id=${jobId}` : "";
  const res = await fetch(`${API_URL}/api/v1/resumes${query}`, { cache: "no-store" });
  return handleResponse<ResumeListItem[]>(res);
}

export async function getResume(id: number): Promise<ResumeDetail> {
  const res = await fetch(`${API_URL}/api/v1/resumes/${id}`, { cache: "no-store" });
  return handleResponse<ResumeDetail>(res);
}

export async function deleteResume(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/resumes/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    await handleResponse(res);
  }
}

export async function deleteCandidate(candidateId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${candidateId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    await handleResponse(res);
  }
}

export interface ResetDataResponse {
  candidates: number;
  resumes: number;
  match_results: number;
  upload_batches: number;
  upload_batch_items: number;
}

export async function resetAllCandidates(): Promise<ResetDataResponse> {
  const res = await fetch(`${API_URL}/api/v1/candidates/reset?confirm=true`, {
    method: "DELETE",
  });
  return handleResponse<ResetDataResponse>(res);
}

export interface CandidateDetailResponse {
  id: number;
  first_name: string | null;
  last_name: string | null;
  email: string;
  phone: string | null;
  linkedin_url: string | null;
  current_location: string | null;
  country: string | null;
  title: string | null;
  passport_number: string | null;
  extracted_data: ExtractedData;
  calculated_metrics: CalculatedMetrics;
  default_resume_id: number | null;
  resumes: ResumeDetail[];
  created_at: string;
  updated_at: string;
}

export interface CandidateProfileUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  current_location?: string | null;
  country?: string | null;
  title?: string | null;
  passport_number?: string | null;
}

export interface DuplicateFieldWarning {
  field: string;
  label: string;
  message: string;
  conflicting_candidate_id: number;
  conflicting_candidate_name: string | null;
  conflicting_candidate_email: string | null;
}

export interface CandidateProfileUpdateResponse {
  saved: boolean;
  duplicate_warnings: DuplicateFieldWarning[];
  candidate: CandidateDetailResponse;
}

export async function getCandidate(candidateId: number): Promise<CandidateDetailResponse> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${candidateId}`, {
    cache: "no-store",
  });
  return handleResponse<CandidateDetailResponse>(res);
}

export async function updateCandidateProfile(
  candidateId: number,
  body: CandidateProfileUpdate
): Promise<CandidateProfileUpdateResponse> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${candidateId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<CandidateProfileUpdateResponse>(res);
}

export type UploadItemStatus = "success" | "skipped" | "error";

export interface ResumeUploadItemResult {
  filename: string;
  status: UploadItemStatus;
  message?: string | null;
  skip_reason?: "duplicate_file" | "duplicate_email" | null;
  duplicate_of_id?: number | null;
  resume?: ResumeDetail | null;
}

export interface BulkResumeUploadResponse {
  total: number;
  succeeded: number;
  skipped: number;
  failed: number;
  results: ResumeUploadItemResult[];
}

export async function uploadResume(file: File): Promise<ResumeDetail> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/api/v1/resumes/upload`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<ResumeDetail>(res);
}

export interface ParsedJobDescription {
  job_title: string | null;
  min_years_experience: number | null;
  max_years_experience: number | null;
  required_skills: string[];
  preferred_skills: string[];
  description: string | null;
  requirements_text: string | null;
  responsibilities_text: string | null;
}

export interface JobDescription {
  id: number;
  title: string;
  raw_text: string;
  parsed: ParsedJobDescription;
  is_active: boolean;
  updated_at: string | null;
  created_at: string | null;
  has_content: boolean;
  is_valid_for_matching: boolean;
  match_count: number;
}

export interface JobDescriptionListItem {
  id: number;
  title: string;
  is_active: boolean;
  is_valid_for_matching: boolean;
  match_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export function isJobMatchableForContext(job: JobDescriptionListItem): boolean {
  return job.is_valid_for_matching || job.match_count > 0;
}

export function isJobDescriptionValid(jd: JobDescription): boolean {
  if (jd.is_valid_for_matching) return true;
  const text = jd.raw_text.trim();
  if (text.length < 40) return false;
  const parsed = jd.parsed;
  return (
    (parsed.required_skills?.length ?? 0) > 0 ||
    (parsed.preferred_skills?.length ?? 0) > 0 ||
    parsed.min_years_experience != null ||
    Boolean(parsed.requirements_text?.trim() && parsed.requirements_text.trim().length >= 20) ||
    Boolean(parsed.description?.trim() && parsed.description.trim().length >= 20)
  );
}

export interface ComponentScoreBreakdown {
  key: string;
  label: string;
  weight_percent: number;
  score: number;
  weighted_points: number;
}

export interface JobDescriptionDeleteResponse {
  deleted_job_id: number;
  deleted_title: string;
  matches_removed: number;
  candidates_preserved: boolean;
  new_active_job_id: number | null;
}

export interface MatchResultDetail {
  resume_id: number;
  job_description_id?: number | null;
  job_title?: string | null;
  candidate_name: string | null;
  filename: string | null;
  rank: number | null;
  final_score: number;
  subtotal_score: number;
  component_scores: Record<string, number>;
  component_breakdown: ComponentScoreBreakdown[];
  matching_skills: string[];
  missing_skills: string[];
  red_flags: Array<{ type: string; description: string; penalty: number }>;
  red_flag_penalty: number;
  strengths: string[];
  weaknesses: string[];
  summary: string;
  matched_at: string;
}

export interface MatchRunResponse {
  job_description_id: number | null;
  job_title: string | null;
  total: number;
  results: MatchResultDetail[];
  matched_new?: number;
  skipped_existing?: number;
}

export async function listJobDescriptions(): Promise<JobDescriptionListItem[]> {
  const res = await fetch(`${API_URL}/api/v1/job-descriptions`, { cache: "no-store" });
  return handleResponse<JobDescriptionListItem[]>(res);
}

export async function getJobDescription(jobId?: number): Promise<JobDescription> {
  const url = jobId
    ? `${API_URL}/api/v1/job-descriptions/${jobId}`
    : `${API_URL}/api/v1/job-description`;
  const res = await fetch(url, { cache: "no-store" });
  return handleResponse<JobDescription>(res);
}

export async function saveJobDescription(
  rawText: string,
  options?: { title?: string | null; jobId?: number }
): Promise<JobDescription> {
  const url = options?.jobId
    ? `${API_URL}/api/v1/job-descriptions/${options.jobId}`
    : `${API_URL}/api/v1/job-description`;
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      raw_text: rawText,
      title: options?.title ?? undefined,
    }),
  });
  return handleResponse<JobDescription>(res);
}

export async function createJobDescription(
  rawText: string,
  options?: { title?: string | null; setAsActive?: boolean }
): Promise<JobDescription> {
  const res = await fetch(`${API_URL}/api/v1/job-descriptions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      raw_text: rawText,
      title: options?.title ?? undefined,
      set_as_active: options?.setAsActive ?? false,
    }),
  });
  return handleResponse<JobDescription>(res);
}

export async function activateJobDescription(jobId: number): Promise<JobDescription> {
  const res = await fetch(`${API_URL}/api/v1/job-descriptions/${jobId}/activate`, {
    method: "POST",
  });
  return handleResponse<JobDescription>(res);
}

export async function deactivateJobDescription(jobId: number): Promise<JobDescription> {
  const res = await fetch(`${API_URL}/api/v1/job-descriptions/${jobId}/deactivate`, {
    method: "POST",
  });
  return handleResponse<JobDescription>(res);
}

export async function deleteJobDescription(
  jobId: number
): Promise<JobDescriptionDeleteResponse> {
  const res = await fetch(`${API_URL}/api/v1/job-descriptions/${jobId}`, {
    method: "DELETE",
  });
  return handleResponse<JobDescriptionDeleteResponse>(res);
}

export function formatJobListLabel(
  title: string,
  matchCount: number,
  isActive: boolean
): string {
  const single = title.replace(/\s+/g, " ").trim();
  const short = single.length > 52 ? `${single.slice(0, 51)}…` : single;
  const prefix = isActive ? "★ " : "";
  return `${prefix}${short} (${matchCount} match${matchCount === 1 ? "" : "es"})`;
}

export async function getJobMatchResults(jobId: number): Promise<MatchRunResponse> {
  const res = await fetch(`${API_URL}/api/v1/job-descriptions/${jobId}/matches`, {
    cache: "no-store",
  });
  return handleResponse<MatchRunResponse>(res);
}

export async function getSampleJobDescription(): Promise<{ raw_text: string }> {
  const res = await fetch(`${API_URL}/api/v1/job-description/sample`, { cache: "no-store" });
  return handleResponse<{ raw_text: string }>(res);
}

export async function runMatching(
  includeLlm = true,
  jobId?: number,
  rematchAll = false
): Promise<MatchRunResponse> {
  const params = new URLSearchParams({
    include_llm: includeLlm ? "true" : "false",
    rematch_all: rematchAll ? "true" : "false",
  });
  if (jobId != null) params.set("job_id", String(jobId));
  const res = await fetch(`${API_URL}/api/v1/matching/run?${params}`, { method: "POST" });
  return handleResponse<MatchRunResponse>(res);
}

export async function runMatchingForCandidate(
  resumeId: number,
  includeLlm = true,
  jobId?: number
): Promise<MatchResultDetail> {
  const params = new URLSearchParams({
    include_llm: includeLlm ? "true" : "false",
  });
  if (jobId != null) params.set("job_id", String(jobId));
  const res = await fetch(
    `${API_URL}/api/v1/matching/run/${resumeId}?${params}`,
    { method: "POST" }
  );
  return handleResponse<MatchResultDetail>(res);
}

export async function getMatchResults(jobId?: number): Promise<MatchRunResponse> {
  const query = jobId != null ? `?job_id=${jobId}` : "";
  const res = await fetch(`${API_URL}/api/v1/matching/results${query}`, {
    cache: "no-store",
  });
  return handleResponse<MatchRunResponse>(res);
}

export async function getMatchResult(
  resumeId: number,
  jobId?: number
): Promise<MatchResultDetail> {
  const query = jobId != null ? `?job_id=${jobId}` : "";
  const res = await fetch(`${API_URL}/api/v1/matching/results/${resumeId}${query}`, {
    cache: "no-store",
  });
  return handleResponse<MatchResultDetail>(res);
}

export async function uploadResumesBulk(files: File[]): Promise<BulkResumeUploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`${API_URL}/api/v1/resumes/upload/bulk`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<BulkResumeUploadResponse>(res);
}

export type DuplicatePolicy = "ignore" | "add_as_default" | "add_as_new_resume";

export interface PrescanFileResult {
  filename: string;
  file_hash: string;
  status: "ok" | "warning" | "error";
  emails_found: string[];
  phones_found?: string[];
  message?: string | null;
  duplicate_of_filename?: string | null;
  duplicate_in_database?: boolean;
  skipped_ai?: boolean;
  processable?: boolean;
}

export interface PrescanResponse {
  total: number;
  ready: number;
  warnings: number;
  errors: number;
  can_proceed: boolean;
  ai_calls_avoided?: number;
  estimated_tokens_saved?: number;
  results: PrescanFileResult[];
}

export interface CandidateProcessResult {
  filename: string;
  status: "success" | "ignored" | "error" | "duplicate_review";
  message?: string | null;
  candidate_id?: number | null;
  resume_id?: number | null;
  is_default?: boolean | null;
  extraction_source?: string | null;
  existing_candidate_id?: number | null;
  parsed_preview?: Record<string, unknown> | null;
  existing_snapshot?: Record<string, unknown> | null;
  duration_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  llm_model?: string | null;
  estimated_cost_usd?: number | null;
  estimated_cost_credits?: number | null;
}

export interface UploadHistoryItem {
  id: number;
  batch_id: number;
  mode: string;
  filename: string;
  process_status?: string | null;
  message?: string | null;
  candidate_id?: number | null;
  resume_id?: number | null;
  duration_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  llm_model?: string | null;
  estimated_cost_usd?: number | null;
  estimated_cost_credits?: number | null;
  created_at: string;
}

export type CostDisplayMode = "usd" | "credits";

export interface ModelPricingEntry {
  model_id: string;
  provider: string;
  label: string;
  input_per_million_usd: number;
  output_per_million_usd: number;
}

export interface ModelPricingSettings {
  cost_display_mode: CostDisplayMode;
  credits_per_usd: number;
  model_pricing: ModelPricingEntry[];
  updated_at?: string | null;
}

export interface SearchContextMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CandidateSearchResultItem {
  candidate_id: number;
  resume_id?: number | null;
  name: string;
  email?: string | null;
  phone?: string | null;
  title?: string | null;
  match_reason?: string | null;
  relevance_score?: number | null;
}

export interface CandidateSearchResponse {
  query: string;
  summary: string;
  results: CandidateSearchResultItem[];
}

export interface BulkCandidateUploadResponse {
  batch_id: number;
  total: number;
  succeeded: number;
  ignored: number;
  failed: number;
  results: CandidateProcessResult[];
}

export async function getUploadHistory(limit = 50): Promise<UploadHistoryItem[]> {
  const res = await fetch(
    `${API_URL}/api/v1/candidates/upload/history?limit=${limit}`,
    { cache: "no-store" }
  );
  return handleResponse<UploadHistoryItem[]>(res);
}

export async function deleteUploadHistoryItem(itemId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/candidates/upload/history/${itemId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    await handleResponse(res);
  }
}

export async function clearUploadHistory(): Promise<{ deleted_items: number }> {
  const res = await fetch(`${API_URL}/api/v1/candidates/upload/history`, {
    method: "DELETE",
  });
  return handleResponse<{ deleted_items: number }>(res);
}

export async function scanCandidateUploads(files: File[]): Promise<PrescanResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const res = await fetch(`${API_URL}/api/v1/candidates/upload/scan`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<PrescanResponse>(res);
}

export async function bulkUploadCandidates(
  files: File[],
  duplicatePolicy: DuplicatePolicy
): Promise<BulkCandidateUploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const res = await fetch(
    `${API_URL}/api/v1/candidates/upload/bulk?duplicate_policy=${duplicatePolicy}`,
    { method: "POST", body: formData }
  );
  return handleResponse<BulkCandidateUploadResponse>(res);
}

export async function singleUploadCandidate(file: File): Promise<CandidateProcessResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/api/v1/candidates/upload/single`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<CandidateProcessResult>(res);
}

export async function confirmSingleUpload(
  file: File,
  duplicatePolicy: DuplicatePolicy
): Promise<CandidateProcessResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(
    `${API_URL}/api/v1/candidates/upload/single/confirm?duplicate_policy=${duplicatePolicy}`,
    { method: "POST", body: formData }
  );
  return handleResponse<CandidateProcessResult>(res);
}

export type LlmProvider = "aws_bedrock" | "openai" | "google";

export interface AppSettings {
  llm_provider: LlmProvider;
  aws_access_key_id: string | null;
  aws_secret_access_key_masked: string | null;
  aws_session_token_masked: string | null;
  aws_secret_configured: boolean;
  aws_session_token_configured: boolean;
  aws_region: string;
  bedrock_model_id: string;
  openai_api_key_masked: string | null;
  openai_api_key_configured: boolean;
  openai_model: string;
  google_api_key_masked: string | null;
  google_api_key_configured: boolean;
  google_model: string;
  updated_at: string | null;
}

export interface SettingsUpdatePayload {
  llm_provider: LlmProvider;
  aws_access_key_id?: string | null;
  aws_secret_access_key?: string | null;
  aws_session_token?: string | null;
  aws_region: string;
  bedrock_model_id: string;
  openai_api_key?: string | null;
  openai_model: string;
  google_api_key?: string | null;
  google_model: string;
}

export type SettingsTestPayload = SettingsUpdatePayload;

export interface SettingsTestResult {
  success: boolean;
  provider: string;
  model: string;
  message: string;
}

export async function getSettings(): Promise<AppSettings> {
  const res = await fetch(`${API_URL}/api/v1/settings`, { cache: "no-store" });
  return handleResponse<AppSettings>(res);
}

export async function saveSettings(payload: SettingsUpdatePayload): Promise<AppSettings> {
  const res = await fetch(`${API_URL}/api/v1/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<AppSettings>(res);
}

export async function testSettings(
  payload: SettingsTestPayload
): Promise<SettingsTestResult> {
  const res = await fetch(`${API_URL}/api/v1/settings/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<SettingsTestResult>(res);
}

export interface DuplicateCheckSettings {
  primary_fields: string[];
  secondary_fields: string[];
  updated_at: string | null;
}

export const DUPLICATE_FIELD_OPTIONS = [
  { id: "email", label: "Email" },
  { id: "phone", label: "Phone" },
] as const;

export async function getDuplicateCheckSettings(): Promise<DuplicateCheckSettings> {
  const res = await fetch(`${API_URL}/api/v1/settings/duplicate-check`, {
    cache: "no-store",
  });
  return handleResponse<DuplicateCheckSettings>(res);
}

export async function saveDuplicateCheckSettings(body: {
  primary_fields: string[];
  secondary_fields: string[];
}): Promise<DuplicateCheckSettings> {
  const res = await fetch(`${API_URL}/api/v1/settings/duplicate-check`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<DuplicateCheckSettings>(res);
}

export async function getModelPricing(): Promise<ModelPricingSettings> {
  const res = await fetch(`${API_URL}/api/v1/settings/pricing`, { cache: "no-store" });
  return handleResponse<ModelPricingSettings>(res);
}

export async function saveModelPricing(body: {
  cost_display_mode: CostDisplayMode;
  credits_per_usd: number;
  model_pricing: ModelPricingEntry[];
}): Promise<ModelPricingSettings> {
  const res = await fetch(`${API_URL}/api/v1/settings/pricing`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<ModelPricingSettings>(res);
}

export async function searchCandidates(
  query: string,
  limit = 15,
  options?: {
    context?: SearchContextMessage[];
    previous_result_ids?: number[];
  }
): Promise<CandidateSearchResponse> {
  const res = await fetch(`${API_URL}/api/v1/candidates/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit,
      context: options?.context ?? [],
      previous_result_ids: options?.previous_result_ids ?? [],
    }),
  });
  return handleResponse<CandidateSearchResponse>(res);
}

export { API_URL };
