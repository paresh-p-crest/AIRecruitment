"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, ExternalLink } from "lucide-react";
import { Header } from "@/components/Header";
import { checkHealth } from "@/lib/api";

const LIVE_APP = "https://ai-recruitment-gamma.vercel.app";
const LIVE_API = "https://airecruitment.onrender.com";

function DocSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="app-surface-card">
      <h2 className="font-display text-xl font-semibold text-white">{title}</h2>
      <div className="mt-4 space-y-3 text-sm leading-relaxed text-slate-300">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-slate-300">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export default function DocumentationPage() {
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    checkHealth().then(setApiOnline).catch(() => setApiOnline(false));
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <Header apiOnline={apiOnline} />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-brand-300">
            <BookOpen className="h-4 w-4" />
            Platform documentation
          </p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Easy AI Recruitment
          </h1>
          <p className="mt-3 text-sm text-slate-400">
            Live app:{" "}
            <a
              href={LIVE_APP}
              className="text-brand-300 underline hover:text-brand-200"
              target="_blank"
              rel="noopener noreferrer"
            >
              {LIVE_APP.replace("https://", "")}
            </a>
          </p>
        </div>

        <div className="space-y-6">
          <DocSection title="Overview">
            <p>
              An AI-powered Recruitment Assistant Platform that transforms the hiring workflow
              through intelligent resume extraction, duplicate-aware candidate management, job
              description matching, and natural-language candidate search.
            </p>
            <p>
              The platform combines conversational search, LangGraph extraction pipelines, and
              hybrid scoring to help recruiters and HR teams upload resumes, structure candidate
              profiles, match talent to roles, and explore the talent pool with AI — reducing
              manual screening time and improving hiring decisions.
            </p>
          </DocSection>

          <DocSection title="Key Features">
            <BulletList
              items={[
                "AI-powered resume extraction from PDF, DOCX, and DOC",
                "Pre-scan duplicate detection before LLM calls (saves tokens and cost)",
                "Configurable duplicate rules (email and phone)",
                "AWS Bedrock LLM integration with Settings UI for credentials, model selection, and connection testing",
                "Per-model token pricing and USD / credits cost display on uploads",
                "Upload history with processing time, tokens, model, and estimated cost",
                "Natural-language candidate search across the full talent pool",
                "Follow-up questions in search (e.g. skills check for a named candidate)",
                "Job description management with per-job match history",
                "Hybrid AI matching: rule-based scoring + LLM summary and skill analysis",
                "Candidate profiles with experience, education, skills, and resume versions",
                "Dashboard with pipeline metrics and top matches",
                "Dark and light theme",
              ]}
            />
          </DocSection>

          <DocSection title="Core Capabilities">
            <BulletList
              items={[
                "LangGraph resume extraction pipeline with structured JSON output",
                "Chunked extraction for large resumes",
                "Identity-based duplicate detection and merge policies",
                "Bulk and single upload with duplicate review workflow",
                "Semantic + keyword candidate search with LLM-ranked results",
                "Job-context matching with component scores and red flags",
                "SQLite persistence with async SQLAlchemy",
                "REST API with OpenAPI / Swagger documentation",
                "Next.js dashboard deployed on Vercel; API on Render",
              ]}
            />
          </DocSection>

          <DocSection title="Business Benefits">
            <BulletList
              items={[
                "Reduces manual resume data entry and screening time",
                "Improves consistency of structured candidate records",
                "Accelerates shortlisting with hybrid match scores",
                "Surfaces best-fit candidates via natural-language search",
                "Tracks LLM usage and estimated cost per upload",
                "Avoids duplicate AI calls with pre-scan gates",
                "Enables 24/7 self-serve recruitment pipeline access via web UI",
              ]}
            />
          </DocSection>

          <DocSection title="Security & Data Handling">
            <p>
              The platform is designed for controlled demo and internal HR use. LLM credentials
              are stored in the application database via Settings (not hard-coded in the frontend).
              Secrets are masked in API responses. CORS is enabled for the deployed frontend.
            </p>
            <p>
              For production, use encrypted secrets management, restrict CORS origins, migrate from
              SQLite to a managed database, and apply your organization&apos;s data retention and
              PII policies for candidate resumes.
            </p>
          </DocSection>

          <DocSection title="Applicable Industries">
            <BulletList
              items={[
                "Staffing and recruitment agencies",
                "Corporate HR and talent acquisition teams",
                "IT services and consulting hiring",
                "Healthcare and clinical recruiting",
                "Finance and professional services hiring",
                "Startup and scale-up recruiting",
                "RPO (Recruitment Process Outsourcing) providers",
                "University and campus hiring programs",
              ]}
            />
          </DocSection>

          <DocSection title="Technology Stack">
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-white">Backend</h3>
                <BulletList
                  items={[
                    "Python 3.11",
                    "FastAPI",
                    "SQLAlchemy (async) + SQLite",
                    "Uvicorn",
                    "Pydantic V2",
                  ]}
                />
              </div>
              <div>
                <h3 className="font-medium text-white">AI & Machine Learning</h3>
                <BulletList
                  items={[
                    "LangChain + LangGraph",
                    "AWS Bedrock (Claude)",
                    "Structured LLM extraction",
                    "Hybrid matching engine + LLM summaries",
                    "Natural-language candidate search",
                    "Optional LangSmith tracing",
                  ]}
                />
              </div>
              <div>
                <h3 className="font-medium text-white">Frontend & Deployment</h3>
                <BulletList
                  items={[
                    "Next.js 15 + React 19",
                    "Tailwind CSS",
                    "Vercel (frontend)",
                    "Render (API)",
                    "REST APIs + OpenAPI / Swagger",
                  ]}
                />
              </div>
            </div>
          </DocSection>

          <DocSection title="Live Demo Links">
            <ul className="space-y-2 text-sm">
              <li>
                <span className="text-slate-500">Web app — </span>
                <a
                  href={LIVE_APP}
                  className="inline-flex items-center gap-1 text-brand-300 underline hover:text-brand-200"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {LIVE_APP}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </li>
              <li>
                <span className="text-slate-500">API — </span>
                <a
                  href={LIVE_API}
                  className="inline-flex items-center gap-1 text-brand-300 underline hover:text-brand-200"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {LIVE_API}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </li>
              <li>
                <span className="text-slate-500">API health — </span>
                <a
                  href={`${LIVE_API}/health`}
                  className="text-brand-300 underline hover:text-brand-200"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {LIVE_API}/health
                </a>
              </li>
              <li>
                <span className="text-slate-500">API docs — </span>
                <a
                  href={`${LIVE_API}/docs`}
                  className="text-brand-300 underline hover:text-brand-200"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {LIVE_API}/docs
                </a>
              </li>
            </ul>
            <p className="mt-3 text-xs text-slate-500">
              Vercel env: <code className="text-slate-400">NEXT_PUBLIC_API_URL={LIVE_API}</code>
            </p>
          </DocSection>

          <DocSection title="One-Line Summary">
            <p className="text-slate-200">
              An AI recruitment platform using FastAPI and Next.js with AWS Bedrock (via LangGraph)
              to extract structured candidate profiles from resumes, run hybrid job matching and
              natural-language search, with duplicate detection, token-cost tracking, and a
              Vercel-hosted demo UI.
            </p>
          </DocSection>

          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/"
              className="rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-400"
            >
              Open recruitment app
            </Link>
            <Link
              href="/settings"
              className="rounded-xl border border-white/15 px-5 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/5"
            >
              Settings
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
