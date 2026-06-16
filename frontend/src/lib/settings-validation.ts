import type { LlmProvider } from "@/lib/api";

export interface LlmSettingsFormState {
  provider: LlmProvider;
  awsAccessKeyId: string;
  awsSecretKey: string;
  openaiKey: string;
  googleKey: string;
  googleModel: string;
}

export interface LlmSettingsConfiguredState {
  secretConfigured: boolean;
  openaiConfigured: boolean;
  googleConfigured: boolean;
}

/** Returns a user-facing message when required fields are missing; null if OK to save/test. */
export function validateLlmSettings(
  form: LlmSettingsFormState,
  configured: LlmSettingsConfiguredState
): string | null {
  if (form.provider === "google" && !form.googleModel.trim()) {
    return "Please select or enter a Gemini model ID.";
  }

  if (form.provider === "aws_bedrock") {
    if (!form.awsAccessKeyId.trim()) {
      return "AWS Access Key ID is required.";
    }
    if (!form.awsSecretKey.trim() && !configured.secretConfigured) {
      return "AWS Secret Access Key is required. Leave blank only when a key is already saved.";
    }
    return null;
  }

  if (form.provider === "openai") {
    if (!form.openaiKey.trim() && !configured.openaiConfigured) {
      return "OpenAI API key is required. Leave blank only when a key is already saved.";
    }
    return null;
  }

  if (form.provider === "google") {
    if (!form.googleKey.trim() && !configured.googleConfigured) {
      return "Google AI API key is required. Leave blank only when a key is already saved.";
    }
    return null;
  }

  return null;
}
