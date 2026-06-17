# Host FastAPI backend on Render (free tier)

**Vercel cannot run this backend.** Vercel is for the Next.js frontend only.  
**Render** is the closest free alternative: connect GitHub, set env vars, get a URL like `https://slicehrms-api.onrender.com`.

That URL is what you put in Vercel as `NEXT_PUBLIC_API_URL`.

---

## Before you start

- [ ] Code is pushed to **GitHub** (see `DEPLOY_VERCEL.md` Part 1)
- [ ] **AWS Bedrock** credentials will be entered in **Settings → LLM Model** after deploy (not in Render env vars)
- [ ] Free tier **sleeps after ~15 min** idle — first request may take 30–60 seconds (cold start)
- [ ] SQLite on `/tmp` — data may reset on redeploy (OK for demo; use Postgres later for production)

---

## Step 1 — Create Render account

1. Go to [https://render.com](https://render.com)
2. Sign up with **GitHub** (same account as your repo)

---

## Step 2 — New Web Service

1. Dashboard → **New +** → **Web Service**
2. **Connect** your GitHub repository (`AI_Recruitment_Demo` or your repo name)
3. If asked, grant Render access to the repo

---

## Step 3 — Service settings

| Field | Value |
|--------|--------|
| **Name** | `slicehrms-api` (or any name) |
| **Region** | Choose nearest to you |
| **Branch** | `main` |
| **Root Directory** | *(leave empty — repo root)* |
| **Runtime** | **Python 3** |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | **Free** |

Render sets `$PORT` automatically — do not hardcode `8000`.

---

## Step 4 — Environment variables

LLM and **AWS Bedrock** keys are **not** required here. They are saved in the app database via **Settings → LLM Model** (same as local).

In the Render **Environment** tab, add only:

### Required

| Key | Value | Notes |
|-----|--------|--------|
| `DATABASE_URL` | `sqlite+aiosqlite:////tmp/recruitment.db` | Writable path on Render |
| `PYTHON_VERSION` | `3.11.9` | Matches local Python 3.11 |

### Recommended

| Key | Value | Notes |
|-----|--------|--------|
| `USE_TEXTRACT` | `true` | PDF text extraction (uses AWS creds from Settings) |

### Optional

| Key | Value | Notes |
|-----|--------|--------|
| `LANGCHAIN_TRACING_V2` | `true` | LangSmith tracing only |
| `LANGCHAIN_API_KEY` | your key | LangSmith only |
| `LANGCHAIN_PROJECT` | `ai-recruitment-demo` | LangSmith only |

### Do not add on Render (use Settings UI instead)

| Do not set | Why |
|------------|-----|
| `OPENAI_API_KEY` | Configure in **Settings → LLM Model** if needed |
| `GOOGLE_API_KEY` | Configure in **Settings → LLM Model** if needed |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Configure in **Settings → LLM Model** |
| `LLM_PROVIDER` / `BEDROCK_MODEL_ID` | Defaults to Bedrock; change in Settings |

After the service is live, open your Vercel app → **Settings → LLM Model** → enter AWS Bedrock keys → **Save** → **Test Connection**.

See `.env.example` for the minimal local `.env` (database + `USE_TEXTRACT` only).

---

## Step 5 — Deploy

1. Click **Create Web Service**
2. Wait for build (5–10 min first time)
3. When status is **Live**, open:

   `https://YOUR-SERVICE-NAME.onrender.com/health`

   You should see JSON with `"status": "ok"`.

4. Your **`NEXT_PUBLIC_API_URL`** for Vercel is:

   ```
   https://YOUR-SERVICE-NAME.onrender.com
   ```

   No trailing slash, no `/health`.

---

## Step 6 — Connect Vercel frontend

1. Vercel project → **Settings** → **Environment Variables**
2. Add:

   | Name | Value |
   |------|--------|
   | `NEXT_PUBLIC_API_URL` | `https://YOUR-SERVICE-NAME.onrender.com` |

3. **Deployments** → **Redeploy** (required after env change)
4. Open your Vercel URL — header should show **API Connected**

---

## Step 7 — Configure AWS Bedrock on live site

1. Open `https://your-app.vercel.app/settings`
2. **LLM Model** → **AWS Bedrock** tab
3. Enter Access Key, Secret Key, Session Token (if sandbox), Region, and Model
4. **Save Settings** → **Test Connection**
5. Upload a test resume on the **Upload** tab

Credentials are stored in the backend database — you do not need them in Render or Vercel env vars.

---

## Using `render.yaml` (optional)

This repo includes `render.yaml`. After pushing to GitHub:

1. Render → **New +** → **Blueprint**
2. Select the repo — Render reads `render.yaml` automatically
3. No secret LLM keys needed in Render — add **AWS Bedrock** in the app **Settings** after deploy

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Build fails on `tika` / Java | Free tier may lack Java; DOC upload might fail — PDF/DOCX usually OK |
| 502 / timeout on upload | Cold start — wait 60s and retry; or upgrade plan |
| API Connected but upload fails | Open **Settings → LLM Model**, save Bedrock keys, Test Connection; check Render **Logs** |
| Data gone after redeploy | Expected with `/tmp` SQLite — re-upload resumes or add Postgres later |
| CORS error | Backend already allows `*` — ensure `NEXT_PUBLIC_API_URL` has no typo |

---

## Other free hosts (alternatives)

| Platform | Notes |
|----------|--------|
| **Railway** | $5 free credit/month; similar setup, `uvicorn` + `$PORT` |
| **Fly.io** | CLI deploy; small free allowance |
| **Koyeb** | Free tier web service |

Render is recommended for the simplest GitHub → URL flow.

---

## Summary

```
GitHub repo
    ├── Render  →  https://slicehrms-api.onrender.com     (FastAPI)
    └── Vercel  →  https://your-app.vercel.app            (Next.js)
                      NEXT_PUBLIC_API_URL = Render URL
```
