"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { useDialog } from "@/components/DialogProvider";
import { AppearanceSection } from "@/components/settings/AppearanceSection";
import { DuplicateDetectionSection } from "@/components/settings/DuplicateDetectionSection";
import { LlmSettingsSection } from "@/components/settings/LlmSettingsSection";
import { ModelPricingSection } from "@/components/settings/ModelPricingSection";
import {
  SettingsNav,
  type SettingsSection,
} from "@/components/settings/SettingsNav";
import { Header } from "@/components/Header";
import {
  API_URL,
  checkHealth,
  getDuplicateCheckSettings,
  getSettings,
  saveDuplicateCheckSettings,
  saveSettings,
  testSettings,
  type AppSettings,
  type LlmProvider,
  type SettingsUpdatePayload,
} from "@/lib/api";
import { getActiveModel } from "@/lib/providers";
import { validateLlmSettings } from "@/lib/settings-validation";

const GOOGLE_MODEL_IDS = [
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "gemini-2.5-pro",
  "gemini-3.5-flash",
  "gemini-3.1-flash-lite",
  "gemini-3-flash-preview",
  "gemini-3.1-pro-preview",
  "gemini-flash-latest",
  "gemini-flash-lite-latest",
  "gemini-pro-latest",
];

const PROVIDER_TABS: { id: LlmProvider; label: string }[] = [
  { id: "aws_bedrock", label: "AWS Bedrock" },
  { id: "openai", label: "OpenAI" },
  { id: "google", label: "Google AI" },
];

export default function SettingsPage() {
  const { alert } = useDialog();
  const [section, setSection] = useState<SettingsSection>("llm");
  const [apiOnline, setApiOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [primaryFields, setPrimaryFields] = useState<string[]>(["email", "phone"]);
  const [dupSaving, setDupSaving] = useState(false);
  const [dupSaved, setDupSaved] = useState(false);

  const [provider, setProvider] = useState<LlmProvider>("aws_bedrock");
  const [savedProvider, setSavedProvider] = useState<LlmProvider>("aws_bedrock");
  const [savedModel, setSavedModel] = useState("");
  const [awsAccessKeyId, setAwsAccessKeyId] = useState("");
  const [awsSecretKey, setAwsSecretKey] = useState("");
  const [awsSessionToken, setAwsSessionToken] = useState("");
  const [awsRegion, setAwsRegion] = useState("us-east-1");
  const [bedrockModel, setBedrockModel] = useState(
    "anthropic.claude-3-sonnet-20240229-v1:0"
  );
  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiModel, setOpenaiModel] = useState("gpt-4o-mini");
  const [googleKey, setGoogleKey] = useState("");
  const [googleModel, setGoogleModel] = useState("gemini-2.5-flash");
  const [googleCustomModel, setGoogleCustomModel] = useState("");

  const [secretConfigured, setSecretConfigured] = useState(false);
  const [sessionConfigured, setSessionConfigured] = useState(false);
  const [openaiConfigured, setOpenaiConfigured] = useState(false);
  const [googleConfigured, setGoogleConfigured] = useState(false);
  const [maskedSecret, setMaskedSecret] = useState<string | null>(null);
  const [maskedSession, setMaskedSession] = useState<string | null>(null);
  const [maskedOpenai, setMaskedOpenai] = useState<string | null>(null);
  const [maskedGoogle, setMaskedGoogle] = useState<string | null>(null);

  const refreshApiStatus = useCallback(async () => {
    const online = await checkHealth();
    setApiOnline(online);
    return online;
  }, []);

  const loadSettings = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
    }
    setError(null);
    const online = await refreshApiStatus();
    if (!online) {
      setError(
        `Cannot reach the API at ${API_URL}. Start the backend with: uvicorn main:app --reload --host 0.0.0.0 --port 8000`
      );
      if (!options?.silent) {
        setLoading(false);
      }
      return;
    }
    try {
      const data: AppSettings = await getSettings();
      setProvider(data.llm_provider);
      setSavedProvider(data.llm_provider);
      setSavedModel(getActiveModel(data));
      setAwsAccessKeyId(data.aws_access_key_id ?? "");
      setAwsRegion(data.aws_region);
      setBedrockModel(data.bedrock_model_id);
      setOpenaiModel(data.openai_model);

      const knownGoogle = GOOGLE_MODEL_IDS.includes(data.google_model);
      if (knownGoogle) {
        setGoogleModel(data.google_model);
        setGoogleCustomModel("");
      } else {
        setGoogleModel("custom");
        setGoogleCustomModel(data.google_model);
      }

      setSecretConfigured(data.aws_secret_configured);
      setSessionConfigured(data.aws_session_token_configured);
      setOpenaiConfigured(data.openai_api_key_configured);
      setGoogleConfigured(data.google_api_key_configured);
      setMaskedSecret(data.aws_secret_access_key_masked);
      setMaskedSession(data.aws_session_token_masked);
      setMaskedOpenai(data.openai_api_key_masked);
      setMaskedGoogle(data.google_api_key_masked);
      setAwsSecretKey("");
      setAwsSessionToken("");
      setOpenaiKey("");
      setGoogleKey("");

      const dup = await getDuplicateCheckSettings();
      setPrimaryFields(dup.primary_fields);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load settings";
      setError(
        message === "Failed to fetch"
          ? `Cannot reach the API at ${API_URL}. Make sure the FastAPI backend is running on port 8000.`
          : message
      );
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  }, [refreshApiStatus]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const resolvedGoogleModel =
    googleModel === "custom" ? googleCustomModel.trim() : googleModel;

  const toggleField = (
    field: string,
    list: string[],
    setter: (v: string[]) => void
  ) => {
    setter(
      list.includes(field) ? list.filter((f) => f !== field) : [...list, field]
    );
    setDupSaved(false);
  };

  const handleSaveDuplicateSettings = async () => {
    setDupSaving(true);
    setDupSaved(false);
    try {
      await saveDuplicateCheckSettings({
        primary_fields: primaryFields,
        secondary_fields: [],
      });
      setDupSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save duplicate settings");
    } finally {
      setDupSaving(false);
    }
  };

  const getValidationError = () =>
    validateLlmSettings(
      {
        provider,
        awsAccessKeyId,
        awsSecretKey,
        openaiKey,
        googleKey,
        googleModel: resolvedGoogleModel,
      },
      {
        secretConfigured,
        openaiConfigured,
        googleConfigured,
      }
    );

  const buildSettingsPayload = (): SettingsUpdatePayload => ({
    llm_provider: provider,
    aws_access_key_id: awsAccessKeyId || null,
    aws_secret_access_key: awsSecretKey || undefined,
    aws_session_token: awsSessionToken || undefined,
    aws_region: awsRegion,
    bedrock_model_id: bedrockModel,
    openai_api_key: openaiKey || undefined,
    openai_model: openaiModel,
    google_api_key: googleKey || undefined,
    google_model: resolvedGoogleModel,
  });

  const handleSave = async () => {
    setSaved(false);
    setTestResult(null);
    setError(null);

    const validationError = getValidationError();
    if (validationError) {
      await alert({
        title: "Cannot save settings",
        message: validationError,
        variant: "warning",
      });
      return;
    }

    setSaving(true);
    const online = await refreshApiStatus();
    if (!online) {
      await alert({
        title: "Backend offline",
        message:
          "Start the API first: uvicorn main:app --reload --host 0.0.0.0 --port 8000",
        variant: "error",
      });
      setSaving(false);
      return;
    }
    try {
      await saveSettings(buildSettingsPayload());
      setSaved(true);
      await loadSettings({ silent: true });
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save settings";
      setError(message);
      await alert({
        title: "Save failed",
        message,
        variant: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTestResult(null);
    setError(null);

    const validationError = getValidationError();
    if (validationError) {
      await alert({
        title: "Cannot test connection",
        message: validationError,
        variant: "warning",
      });
      return;
    }

    setTesting(true);
    const online = await refreshApiStatus();
    if (!online) {
      setTestResult({
        success: false,
        message: "Backend is offline. Start FastAPI on port 8000, then try again.",
      });
      setTesting(false);
      return;
    }
    try {
      const result = await testSettings(buildSettingsPayload());
      const tabLabel = PROVIDER_TABS.find((t) => t.id === provider)?.label ?? provider;
      const inUseNote =
        provider !== savedProvider
          ? ` (${tabLabel} tested — ${PROVIDER_TABS.find((t) => t.id === savedProvider)?.label ?? savedProvider} still in use for extraction)`
          : "";
      setTestResult({
        success: result.success,
        message: `${result.message}${inUseNote}`,
      });
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : "Test failed",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        apiOnline={apiOnline}
        activeProvider={savedProvider}
        activeModel={savedModel || undefined}
      />

      <div className="mx-auto flex w-full max-w-[1800px] flex-1 flex-col lg:flex-row">
        <SettingsNav active={section} onChange={setSection} />

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {!apiOnline && !loading && (
            <div className="mb-6 flex flex-col gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-2">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  Backend API is offline at{" "}
                  <code className="text-amber-100">{API_URL}</code>.
                </span>
              </div>
              <button
                type="button"
                onClick={() => loadSettings()}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-500/30 px-3 py-1.5 text-xs font-medium hover:bg-amber-500/10"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          )}

          {loading && section !== "appearance" && section !== "pricing" ? (
            <div className="flex items-center justify-center py-24 text-slate-500">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading settings…
            </div>
          ) : (
            <div className="max-w-3xl">
              {section === "llm" && !loading && (
                <LlmSettingsSection
                  provider={provider}
                  onProviderChange={setProvider}
                  savedProvider={savedProvider}
                  savedModel={savedModel}
                  awsAccessKeyId={awsAccessKeyId}
                  onAwsAccessKeyIdChange={setAwsAccessKeyId}
                  awsSecretKey={awsSecretKey}
                  onAwsSecretKeyChange={setAwsSecretKey}
                  awsSessionToken={awsSessionToken}
                  onAwsSessionTokenChange={setAwsSessionToken}
                  awsRegion={awsRegion}
                  onAwsRegionChange={setAwsRegion}
                  bedrockModel={bedrockModel}
                  onBedrockModelChange={setBedrockModel}
                  openaiKey={openaiKey}
                  onOpenaiKeyChange={setOpenaiKey}
                  openaiModel={openaiModel}
                  onOpenaiModelChange={setOpenaiModel}
                  googleKey={googleKey}
                  onGoogleKeyChange={setGoogleKey}
                  googleModel={googleModel}
                  onGoogleModelChange={setGoogleModel}
                  googleCustomModel={googleCustomModel}
                  onGoogleCustomModelChange={setGoogleCustomModel}
                  secretConfigured={secretConfigured}
                  sessionConfigured={sessionConfigured}
                  openaiConfigured={openaiConfigured}
                  googleConfigured={googleConfigured}
                  maskedSecret={maskedSecret}
                  maskedSession={maskedSession}
                  maskedOpenai={maskedOpenai}
                  maskedGoogle={maskedGoogle}
                  error={error}
                  testResult={testResult}
                  saving={saving}
                  saved={saved}
                  testing={testing}
                  onSave={handleSave}
                  onTest={handleTest}
                />
              )}

              {section === "duplicate" && !loading && apiOnline && (
                <DuplicateDetectionSection
                  primaryFields={primaryFields}
                  onTogglePrimary={(field) =>
                    toggleField(field, primaryFields, setPrimaryFields)
                  }
                  saving={dupSaving}
                  saved={dupSaved}
                  onSave={handleSaveDuplicateSettings}
                />
              )}

              {section === "duplicate" && !loading && !apiOnline && (
                <p className="text-sm text-slate-500">
                  Connect to the backend to configure duplicate detection rules.
                </p>
              )}

              {section === "pricing" && <ModelPricingSection apiOnline={apiOnline} />}

              {section === "appearance" && <AppearanceSection />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
