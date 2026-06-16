# AI Recruitment Assistant Platform

Full-stack demo for **Phase 1 (Resume Upload)** and **Phase 2 (Data Extraction)** — FastAPI backend + Next.js UI deployable to Vercel.

## Tech Stack

| Layer | Tool |
|-------|------|
| API | FastAPI (async uploads) |
| AI | LangChain + LangGraph |
| LLM | AWS Bedrock (Claude 3 Sonnet) or OpenAI `gpt-4o-mini` |
| Settings UI | Configure credentials at `/settings` (stored in SQLite) |
| Tracing | LangSmith |
| Database | SQLAlchemy + SQLite (async) |
| Parsing | pdfplumber (PDF), python-docx (DOCX) |
| Validation | Pydantic V2 |
| UI | Next.js 15 + Tailwind CSS (Vercel-ready) |

## Project Structure

```
├── main.py              # FastAPI app, routes, startup
├── graph.py             # LangGraph extraction pipeline
├── schemas.py           # Pydantic models
├── models.py            # SQLAlchemy ORM models
├── database.py          # Async SQLite session setup
├── utils.py             # PDF/DOCX text extraction
├── frontend/            # Next.js UI (deploy to Vercel)
│   ├── src/app/         # Pages and layout
│   ├── src/components/  # Upload, list, detail views
│   └── src/lib/api.ts   # API client
├── requirements.txt
├── .env.example
└── README.md
```

## Quick Start

### 1. Virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` (optional — you can also use the **Settings page** in the UI):

```env
LLM_PROVIDER=aws_bedrock

# AWS Bedrock (sandbox / IAM credentials)
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_SESSION_TOKEN=your-session-token   # required for temporary sandbox creds
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Or OpenAI instead
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini

DATABASE_URL=sqlite+aiosqlite:///./recruitment.db
```

**Recommended:** Open http://localhost:3000/settings, select **AWS Bedrock**, paste your sandbox credentials (including Session Token), click **Save** then **Test Connection**.

**LangSmith setup**

1. Create an account at [smith.langchain.com](https://smith.langchain.com)
2. Generate an API key under **Settings → API Keys**
3. Set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` in `.env`
4. Traces from the LangGraph pipeline appear automatically in your LangSmith project

### 4. Run the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 5. Run the UI (separate terminal)

```bash
cd frontend
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

- UI: http://localhost:3000

The UI provides drag-and-drop resume upload, a candidate list, and a detailed profile view (personal info, experience, education, skills).

## Deploy to Production

### Frontend → Vercel

1. Push the repo to GitHub
2. Import the project in [vercel.com](https://vercel.com) — set **Root Directory** to `frontend`
3. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-api-domain.com`
4. Deploy

### Backend → Railway / Render / Fly.io

Deploy the FastAPI app separately (Vercel cannot host long-running Python APIs with SQLite persistence). Example platforms:

- **Railway** — `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Render** — Web Service with the same start command

Set `OPENAI_API_KEY` and optional LangSmith vars in the hosting dashboard. Update CORS in `main.py` if you restrict origins in production.

> **Why Next.js over Streamlit?** Streamlit is faster to prototype but limited for polished, mobile-friendly UIs and Vercel deployment. Next.js gives a production-grade interface that talks to your existing FastAPI API.

## API Endpoints

### `POST /api/v1/resumes/upload`

Upload a `.pdf` or `.docx` resume. The server:

1. Extracts raw text from the document
2. Runs the LangGraph pipeline (LLM extraction → experience calculation)
3. Saves raw text + structured JSON to SQLite
4. Returns the full structured response

**Example (curl):**

```bash
curl -X POST "http://localhost:8000/api/v1/resumes/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/resume.pdf"
```

### `GET /api/v1/resumes`

Returns a list of all parsed candidates with summary fields (name, email, total experience).

### `GET /api/v1/resumes/{id}`

Returns full structured data for a single candidate (used by the UI detail panel).

### `DELETE /api/v1/resumes/{id}`

Permanently deletes a candidate resume record.

### `GET /api/v1/settings`

Returns current LLM provider settings (secrets are masked).

### `PUT /api/v1/settings`

Update provider (`aws_bedrock` or `openai`) and credentials. Leave secret fields empty to keep existing values.

### `POST /api/v1/settings/test`

Test the configured LLM connection with a minimal prompt.

## LangGraph Pipeline

```
raw_text → [LLM Extraction] → [Business Logic] → parsed_json + calculated_metrics
```

| Node | Responsibility |
|------|----------------|
| **LLM Extraction** | `ChatOpenAI(gpt-4o-mini).with_structured_output(ExtractedResume)` |
| **Business Logic** | Computes `Total_Years_Of_Experience` from employment date ranges |

## Extracted Schema (`ExtractedResume`)

- **Personal_Info** — name, email, phone, location, current company/designation
- **Professional_Experience** — company, title, dates, responsibilities, technologies
- **Education** — degree, college, years, grade/CGPA
- **Skills** — technical and soft skills
- **Calculated metrics** — `Total_Years_Of_Experience` (float)

## Error Handling

- Unsupported file types → `400 Bad Request`
- Empty or unreadable documents → `422 Unprocessable Entity`
- Files over 10 MB → `413 Request Entity Too Large`
- Missing `OPENAI_API_KEY` or LLM failures → `500` / `502`
