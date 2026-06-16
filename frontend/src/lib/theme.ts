export type AppTheme = "dark" | "light";

export const THEME_STORAGE_KEY = "slicehrms-theme";

export const DEFAULT_THEME: AppTheme = "dark";

export function isAppTheme(value: string | null | undefined): value is AppTheme {
  return value === "dark" || value === "light";
}

export function readStoredTheme(): AppTheme {
  if (typeof window === "undefined") {
    return DEFAULT_THEME;
  }
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isAppTheme(stored) ? stored : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

export function applyTheme(theme: AppTheme) {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme;
}
