"use client";

import {
  AlertCircle,
  CheckCircle2,
  Cloud,
  KeyRound,
  Loader2,
  Save,
  Sparkles,
  Zap,
} from "lucide-react";
import { ActiveProviderBadge } from "@/components/ActiveProviderBadge";
import { TabBar } from "@/components/TabBar";
import type { LlmProvider } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Field, SectionHeader, SelectField } from "./settings-fields";

const PROVIDER_TABS: { id: LlmProvider; label: string }[] = [
  { id: "aws_bedrock", label: "AWS Bedrock" },
  { id: "openai", label: "OpenAI" },
  { id: "google", label: "Google AI" },
];

const BEDROCK_MODELS = [
  "anthropic.claude-3-sonnet-20240229-v1:0",
  "anthropic.claude-3-haiku-20240307-v1:0",
  "anthropic.claude-3-5-sonnet-20240620-v1:0",
];

const AWS_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"];

const GOOGLE_MODELS = [
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash (recommended)" },
  { id: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
  { id: "gemini-3.1-flash-lite", label: "Gemini 3.1 Flash Lite" },
  { id: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview" },
  { id: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview" },
  { id: "gemini-flash-latest", label: "Gemini Flash Latest" },
  { id: "gemini-flash-lite-latest", label: "Gemini Flash Lite Latest" },
  { id: "gemini-pro-latest", label: "Gemini Pro Latest" },
];

const PROVIDER_TIPS: Record<LlmProvider, string> = {
  aws_bedrock:
    "Save to set Bedrock as the active provider. Test Connection checks this tab only — other providers keep their saved keys.",
  openai:
    "Save to switch extraction to OpenAI. Test Connection validates this tab even when another provider is in use.",
  google:
    "Save to switch extraction to Google AI. Test Connection validates this tab without clearing other saved keys.",
};

export interface LlmSettingsSectionProps {
  provider: LlmProvider;
  onProviderChange: (provider: LlmProvider) => void;
  savedProvider: LlmProvider;
  savedModel: string;
  awsAccessKeyId: string;
  onAwsAccessKeyIdChange: (v: string) => void;
  awsSecretKey: string;
  onAwsSecretKeyChange: (v: string) => void;
  awsSessionToken: string;
  onAwsSessionTokenChange: (v: string) => void;
  awsRegion: string;
  onAwsRegionChange: (v: string) => void;
  bedrockModel: string;
  onBedrockModelChange: (v: string) => void;
  openaiKey: string;
  onOpenaiKeyChange: (v: string) => void;
  openaiModel: string;
  onOpenaiModelChange: (v: string) => void;
  googleKey: string;
  onGoogleKeyChange: (v: string) => void;
  googleModel: string;
  onGoogleModelChange: (v: string) => void;
  googleCustomModel: string;
  onGoogleCustomModelChange: (v: string) => void;
  secretConfigured: boolean;
  sessionConfigured: boolean;
  openaiConfigured: boolean;
  googleConfigured: boolean;
  maskedSecret: string | null;
  maskedSession: string | null;
  maskedOpenai: string | null;
  maskedGoogle: string | null;
  error: string | null;
  testResult: { success: boolean; message: string } | null;
  saving: boolean;
  saved: boolean;
  testing: boolean;
  onSave: () => void;
  onTest: () => void;
}

export function LlmSettingsSection({
  provider,
  onProviderChange,
  savedProvider,
  savedModel,
  awsAccessKeyId,
  onAwsAccessKeyIdChange,
  awsSecretKey,
  onAwsSecretKeyChange,
  awsSessionToken,
  onAwsSessionTokenChange,
  awsRegion,
  onAwsRegionChange,
  bedrockModel,
  onBedrockModelChange,
  openaiKey,
  onOpenaiKeyChange,
  openaiModel,
  onOpenaiModelChange,
  googleKey,
  onGoogleKeyChange,
  googleModel,
  onGoogleModelChange,
  googleCustomModel,
  onGoogleCustomModelChange,
  secretConfigured,
  sessionConfigured,
  openaiConfigured,
  googleConfigured,
  maskedSecret,
  maskedSession,
  maskedOpenai,
  maskedGoogle,
  error,
  testResult,
  saving,
  saved,
  testing,
  onSave,
  onTest,
}: LlmSettingsSectionProps) {
  const hasUnsavedProviderChange = provider !== savedProvider;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-semibold text-white">LLM Model</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          Configure AI providers for resume extraction. Only one provider is active at a time;
          credentials for all tabs are kept when you switch.
        </p>
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Currently active for extraction
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {savedModel ? (
            <ActiveProviderBadge provider={savedProvider} model={savedModel} />
          ) : (
            <span className="text-sm text-slate-400">No provider configured yet</span>
          )}
          {hasUnsavedProviderChange && (
            <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-medium text-amber-300 ring-1 ring-amber-500/30">
              Unsaved — Save to switch to{" "}
              {PROVIDER_TABS.find((t) => t.id === provider)?.label}
            </span>
          )}
        </div>
      </div>

      <TabBar
        active={provider}
        onChange={onProviderChange}
        tabs={PROVIDER_TABS.map((tab) => ({
          ...tab,
          badge: tab.id === savedProvider ? "In use" : undefined,
        }))}
      />

      <section className="glass animate-fade-in rounded-2xl p-6 shadow-card">
        {provider === "aws_bedrock" && (
          <>
            <SectionHeader icon={Cloud} title="AWS Bedrock" />
            <div className="space-y-4">
              <Field
                label="Access Key ID"
                value={awsAccessKeyId}
                onChange={onAwsAccessKeyIdChange}
                placeholder="AKIA..."
              />
              <Field
                label="Secret Access Key"
                value={awsSecretKey}
                onChange={onAwsSecretKeyChange}
                placeholder={
                  secretConfigured
                    ? `Saved: ${maskedSecret} — leave blank to keep`
                    : "Paste secret access key"
                }
                type="password"
              />
              <Field
                label="Session Token (sandbox / temp creds)"
                value={awsSessionToken}
                onChange={onAwsSessionTokenChange}
                placeholder={
                  sessionConfigured
                    ? `Saved: ${maskedSession} — leave blank to keep`
                    : "Optional for temporary AWS credentials"
                }
                type="password"
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <SelectField
                  label="AWS Region"
                  value={awsRegion}
                  onChange={onAwsRegionChange}
                  options={AWS_REGIONS}
                />
                <SelectField
                  label="Bedrock Model"
                  value={bedrockModel}
                  onChange={onBedrockModelChange}
                  options={BEDROCK_MODELS}
                />
              </div>
            </div>
          </>
        )}

        {provider === "openai" && (
          <>
            <SectionHeader icon={KeyRound} title="OpenAI" />
            <div className="space-y-4">
              <Field
                label="API Key"
                value={openaiKey}
                onChange={onOpenaiKeyChange}
                placeholder={
                  openaiConfigured
                    ? `Saved: ${maskedOpenai} — leave blank to keep`
                    : "sk-..."
                }
                type="password"
              />
              <Field
                label="Model"
                value={openaiModel}
                onChange={onOpenaiModelChange}
                placeholder="gpt-4o-mini"
              />
            </div>
          </>
        )}

        {provider === "google" && (
          <>
            <SectionHeader icon={Sparkles} title="Google AI Studio" />
            <div className="space-y-4">
              <Field
                label="API Key (GOOGLE_API_KEY)"
                value={googleKey}
                onChange={onGoogleKeyChange}
                placeholder={
                  googleConfigured
                    ? `Saved: ${maskedGoogle} — leave blank to keep`
                    : "Paste API key from aistudio.google.com"
                }
                type="password"
              />
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-400">
                  Gemini Model
                </label>
                <select
                  value={googleModel}
                  onChange={(e) => onGoogleModelChange(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-brand-500/50"
                >
                  {GOOGLE_MODELS.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                  <option value="custom">Custom model ID…</option>
                </select>
              </div>
              {googleModel === "custom" && (
                <Field
                  label="Custom Model ID"
                  value={googleCustomModel}
                  onChange={onGoogleCustomModelChange}
                  placeholder="e.g. gemini-2.5-flash"
                />
              )}
              <p className="text-xs text-slate-500">
                Get your key at{" "}
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-400 underline hover:text-brand-300"
                >
                  aistudio.google.com/apikey
                </a>
                . Use model IDs exactly as shown in AI Studio.
              </p>
            </div>
          </>
        )}
      </section>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {testResult && (
        <div
          className={cn(
            "flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
            testResult.success
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/30 bg-red-500/10 text-red-300"
          )}
        >
          {testResult.success ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <span className="break-all">{testResult.message}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-400 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : saved ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {saved ? "Saved" : "Save Settings"}
        </button>
        <button
          type="button"
          onClick={onTest}
          disabled={testing}
          className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-5 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/10 disabled:opacity-50"
        >
          {testing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Zap className="h-4 w-4" />
          )}
          Test Connection
        </button>
      </div>

      <p className="text-xs text-slate-500">{PROVIDER_TIPS[provider]}</p>
    </div>
  );
}
