# SliceHRMS — AI Recruitment Demo Recording Script

**Tips before you record**
- Speak slowly; pause half a second between sections.
- Green **API Connected** = backend is running only (not a full AWS test).
- Use **Test Connection** in LLM settings to prove credentials work.
- Total run time: about 8–12 minutes if you follow all sections.

---

## 1. Opening (Home page)

Hello, this is **SliceHRMS — AI Recruitment Assistant**.

This demo walks through the full recruitment flow:

settings, resume upload, AI search, job description, candidates, and matching.

At the top you see the active LLM provider and model, API status, theme toggle, and Settings.

---

## 2. Settings — Overview

I’ll open **Settings** from the header.

The left menu has: **Recruitment** home link, **LLM Model**, **Model Pricing**, **Duplicate Detection**, and **Appearance**.

We’ll configure the app first, then run the recruitment workflow.

---

## 3. Settings — LLM Model

Under **LLM Model**, we choose who powers extraction and search.

Three providers are supported: **AWS Bedrock**, **OpenAI**, and **Google AI**.

Select a tab, enter API keys and model, then **Save Settings**.

**Test Connection** checks only the tab you’re on — it does not change the active provider unless you save.

The badge at the top shows which provider is **in use** for uploads and search.

---

## 4. Settings — Duplicate Detection

Next, **Duplicate Detection**.

Here we define which fields identify the same person: email, phone, LinkedIn, and optional fields like passport.

**Primary** fields block or flag duplicates on upload.

**Secondary** fields warn when editing a profile if another candidate already uses that value.

Click **Save** when your rules are set.

---

## 5. Settings — Model Pricing

**Model Pricing** controls how upload cost is displayed.

In **USD** mode, set input and output price per million tokens for each model.

In **Credits** mode, set how many credits equal one US dollar.

Upload history and batch results use these rates for estimates.

Save when done.

---

## 6. Settings — Appearance (optional, 10 seconds)

**Appearance** switches between dark and light theme.

Default is dark; light mode improves readability in bright rooms.

---

## 7. Dashboard

Back on **Recruitment**, open the **Dashboard** tab.

Here we see pipeline snapshot: total candidates, matched count, average score, and experience.

It shows the active job, file types, and top matches at a glance.

Use the quick links to jump to Upload, Job, Matching, or Candidates.

---

## 8. Upload

Open the **Upload** tab.

Drag and drop PDF, DOCX, or DOC files — or browse to select them.

The app **pre-scans** first: file type, email, and duplicates before calling the LLM.

Review the scan summary, pick a **duplicate policy**, then **Process with AI**.

Each file shows status, model, tokens, and estimated cost in the table.

**Upload history** below keeps past runs with time, tokens, and cost — you can delete one entry or clear all.

---

## 9. Search

Open the **Search** tab.

Type a question in the search box at the bottom — for example, list candidates with more than ten years of experience.

Press **Search** or Enter.

The answer appears above the input, with a results table: name, contact, email, and **View** to open the profile.

You can ask follow-up questions in the same session.

Search runs across **all candidates**, not only the active job.

---

## 10. Job Description (JD)

Open **Job Description**.

Select or create a job posting; each job keeps its own match history.

Edit the title and paste the job text — skills, years of experience, location, and so on.

**Save** stores the JD. **Set as active** makes this the job used for matching.

Archived jobs still show stored scores; matching always uses the **active** job.

---

## 11. Candidates

Open **Candidates**.

This list shows everyone in the pool for the selected job context.

Select a row to open the profile: contact details, experience, education, and skills.

You can edit fields, manage resumes, and run **Match this candidate** for the active job.

Delete removes a candidate when needed.

---

## 12. Match Summary

Open **Match Summary**.

Click **Run matching** to score all candidates against the active job description.

The table shows rank, final score, matching and missing skills, strengths, weaknesses, and summary.

Open a row to see full breakdown and red flags.

Use **Rematch all** to recalculate after JD or candidate changes.

---

## 13. Closing

That completes the SliceHRMS AI recruitment demo:

**Settings** for LLM, duplicates, and pricing;

**Upload** with pre-scan and cost tracking;

**Search** for natural-language candidate discovery;

**Job Description**, **Candidates**, and **Match Summary** for hybrid AI matching.

Thank you for watching.

---

## Quick reference — one line per section

| Section | One-line script |
|--------|------------------|
| Intro | SliceHRMS AI Recruitment — full pipeline from settings to matching. |
| LLM Model | Pick Bedrock, OpenAI, or Google; save keys and test connection. |
| Duplicate Detection | Set primary and secondary fields to catch duplicate candidates. |
| Model Pricing | Configure USD token rates or credits for cost display. |
| Dashboard | Overview of candidates, matches, and active job. |
| Upload | Pre-scan resumes, extract with AI, view tokens and cost. |
| Search | Ask questions; get candidate tables and open profiles. |
| Job Description | Create jobs, set active JD, keep per-job match history. |
| Candidates | Browse profiles, edit, and match individuals. |
| Match Summary | Run hybrid matching and review scores and skills fit. |
| Close | Settings, upload, search, JD, candidates, and match — end to end. |
