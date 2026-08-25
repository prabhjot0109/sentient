import { useEffect, useState } from "react";

/**
 * The browser's own link state. Deliberately NOT used to decide whether a
 * request failed -- navigator.onLine reports that an interface is up, not that
 * anything is reachable, and a captive portal reports true. NetworkError answers
 * "this request could not reach the server"; this answers "the machine thinks it
 * has no network", which is worth saying before the user blames the backend.
 */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);

  return online;
}
