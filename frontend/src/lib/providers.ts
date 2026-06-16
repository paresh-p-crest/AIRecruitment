import type { AppSettings, LlmProvider } from "@/lib/api";

export interface ProviderMeta {
  id: LlmProvider;
  label: string;
  shortLabel: string;
  colorClass: string;
  ringClass: string;
}

export const PROVIDER_META: Record<LlmProvider, ProviderMeta> = {
  aws_bedrock: {
    id: "aws_bedrock",
    label: "AWS Bedrock",
    shortLabel: "Bedrock",
    colorClass: "bg-orange-500/15 text-orange-300",
    ringClass: "ring-orange-500/30",
  },
  openai: {
    id: "openai",
    label: "OpenAI",
    shortLabel: "OpenAI",
    colorClass: "bg-emerald-500/15 text-emerald-300",
    ringClass: "ring-emerald-500/30",
  },
  google: {
    id: "google",
    label: "Google Gemini",
    shortLabel: "Gemini",
    colorClass: "bg-blue-500/15 text-blue-300",
    ringClass: "ring-blue-500/30",
  },
};

export function getActiveModel(settings: AppSettings): string {
  switch (settings.llm_provider) {
    case "aws_bedrock":
      return settings.bedrock_model_id;
    case "openai":
      return settings.openai_model;
    case "google":
      return settings.google_model;
    default:
      return "unknown";
  }
}

export function isProviderConfigured(settings: AppSettings, provider: LlmProvider): boolean {
  switch (provider) {
    case "aws_bedrock":
      return settings.aws_secret_configured;
    case "openai":
      return settings.openai_api_key_configured;
    case "google":
      return settings.google_api_key_configured;
    default:
      return false;
  }
}
