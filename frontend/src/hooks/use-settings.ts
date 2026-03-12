import { useCallback, useSyncExternalStore } from "react";

const API_KEY_STORAGE_KEY = "sentient_api_key";
const SETTINGS_CHANGE_EVENT = "sentient-settings-change";

function getStoredApiKey() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(API_KEY_STORAGE_KEY) || "";
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(SETTINGS_CHANGE_EVENT, callback);

  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(SETTINGS_CHANGE_EVENT, callback);
  };
}

function notifySettingsChange() {
  window.dispatchEvent(new Event(SETTINGS_CHANGE_EVENT));
}

export function useSettings() {
  const apiKey = useSyncExternalStore(subscribe, getStoredApiKey, () => "");

  const setApiKey = useCallback((key: string) => {
    if (key) {
      localStorage.setItem(API_KEY_STORAGE_KEY, key);
    } else {
      localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
    notifySettingsChange();
  }, []);

  const clearApiKey = useCallback(() => {
    setApiKey("");
  }, [setApiKey]);

  return {
    apiKey,
    setApiKey,
    clearApiKey,
    isLoaded: true,
    hasApiKey: Boolean(apiKey),
  };
}
