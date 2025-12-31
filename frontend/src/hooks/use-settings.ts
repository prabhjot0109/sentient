import { useState, useCallback, useSyncExternalStore } from "react";

const API_KEY_STORAGE_KEY = "sentient_api_key";

function getStoredApiKey() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(API_KEY_STORAGE_KEY) || "";
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

export function useSettings() {
  const storedKey = useSyncExternalStore(subscribe, getStoredApiKey, () => "");
  const [apiKey, setApiKeyState] = useState<string>(storedKey);
  const [isLoaded] = useState(true);

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    if (key) {
      localStorage.setItem(API_KEY_STORAGE_KEY, key);
    } else {
      localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
  }, []);

  const clearApiKey = useCallback(() => {
    setApiKeyState("");
    localStorage.removeItem(API_KEY_STORAGE_KEY);
  }, []);

  return {
    apiKey,
    setApiKey,
    clearApiKey,
    isLoaded,
    hasApiKey: Boolean(apiKey),
  };
}
