# Deploy SliceHRMS to GitHub + Vercel

This app has two parts:

| Part | Technology | Host on Vercel? |
|------|------------|-----------------|
| **Frontend** | Next.js (`frontend/`) | **Yes** |
| **Backend** | FastAPI (`main.py`) | **No** — use Render, Railway, Fly.io, or AWS |

Vercel runs the UI. The API must be deployed separately; the frontend calls it via `NEXT_PUBLIC_API_URL`.

---

## Part 1 — Push code to GitHub

### 1. Create a GitHub repository

1. Open [https://github.com/new](https://github.com/new)
2. Repository name: e.g. `ai-recruitment-demo` or `SliceHRMS-AI-Recruitment`
3. **Private** recommended (demo may reference internal HR data patterns)
4. Do **not** add README, .gitignore, or license (we already have them)
5. Click **Create repository**

### 2. Initialize Git locally (if not done yet)

From the project root (`AI_Recruitment_Demo`):

```powershell
cd "d:\AWS\AWS Projects\AI Recruitment - SliceHRMS\AI_Recruitment_Demo"

git init
git add .
git status
```

Confirm `.env` and `frontend/.env.local` are **not** listed (they are in `.gitignore`).

### 3. First commit

```powershell
git commit -m "Initial commit: SliceHRMS AI Recruitment demo"
```

### 4. Connect remote and push

Replace `YOUR_USERNAME` and `YOUR_REPO` with your GitHub details:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

If GitHub asks you to sign in, use a **Personal Access Token** as the password (Settings → Developer settings → Personal access tokens).

---

## Part 2 — Deploy frontend on Vercel

### 1. Import project

1. Go to [https://vercel.com](https://vercel.com) and sign in (use **Continue with GitHub**)
2. **Add New… → Project**
3. Import the repository you just pushed
4. Configure:

| Setting | Value |
|---------|--------|
| **Framework Preset** | Next.js |
| **Root Directory** | `frontend` ← **important** |
| **Build Command** | `npm run build` (default) |
| **Output Directory** | `.next` (default) |

### 2. Environment variables (Vercel)

Before deploying, add:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | Your **backend** URL, e.g. `https://your-api.onrender.com` (no trailing slash) |

For a first deploy **without** a live API, you can use a placeholder; the UI will show **API Offline** until the backend is up.

### 3. Deploy

Click **Deploy**. Vercel will build and give you a URL like `https://your-app.vercel.app`.

---

## Part 3 — Deploy backend (required for full demo)

FastAPI cannot run as the main app on Vercel. Options:

### Option A — Render (simple, free tier)

**Full step-by-step:** see **[DEPLOY_BACKEND_RENDER.md](./DEPLOY_BACKEND_RENDER.md)**

1. [render.com](https://render.com) → **New → Web Service** → connect GitHub repo
2. **Build:** `pip install -r requirements.txt`
3. **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Env:** `DATABASE_URL=sqlite+aiosqlite:////tmp/recruitment.db` and `USE_TEXTRACT=true` only
5. After deploy, set **AWS Bedrock** in app **Settings → LLM Model** (not Render env)
6. Copy Render URL → Vercel `NEXT_PUBLIC_API_URL` → redeploy frontend

### Option B — Railway / Fly.io

Same idea: Python service, `uvicorn main:app`, expose HTTPS URL, point Vercel at it.

### CORS

The backend already allows common origins. If the Vercel domain is blocked, add it in `main.py` CORS `allow_origins`.

---

## Part 4 — After deploy checklist

- [ ] GitHub repo has **no** `.env` or secrets committed
- [ ] Vercel **Root Directory** = `frontend`
- [ ] `NEXT_PUBLIC_API_URL` set in Vercel environment variables
- [ ] Backend `/health` returns OK in browser
- [ ] Settings → **Test Connection** for your LLM provider
- [ ] Upload a test resume end-to-end

---

## Quick commands reference

```powershell
# Daily: push changes
git add .
git commit -m "Describe your change"
git push

# Vercel redeploys automatically on push to main (if connected)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on Vercel | Ensure **Root Directory** is `frontend`, not repo root |
| API Offline on live site | Set `NEXT_PUBLIC_API_URL` and redeploy; check backend is running |
| CORS errors | Add `https://your-app.vercel.app` to backend CORS |
| 404 on refresh | Next.js on Vercel handles this; ensure framework is Next.js |
