export type ThemePreference = "system" | "light" | "dark";
const storageKey = "collabflow_theme";
const subscribers = new Set<() => void>();

export function readThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(storageKey);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function applyTheme(preference: ThemePreference) {
  const effective = preference === "system"
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme = effective;
}

export function updateThemePreference(preference: ThemePreference) {
  try { localStorage.setItem(storageKey, preference); } catch { /* Keep the selection for this session. */ }
  applyTheme(preference);
  subscribers.forEach(notify => notify());
}

export function subscribeThemePreference(notify: () => void) {
  subscribers.add(notify);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onStorage = (event: StorageEvent) => {
    if (event.key === storageKey || event.key === null) {
      applyTheme(readThemePreference());
      notify();
    }
  };
  const onSystemChange = () => {
    if (readThemePreference() === "system") applyTheme("system");
  };
  window.addEventListener("storage", onStorage);
  media.addEventListener("change", onSystemChange);
  return () => {
    subscribers.delete(notify);
    window.removeEventListener("storage", onStorage);
    media.removeEventListener("change", onSystemChange);
  };
}
