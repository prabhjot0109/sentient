import { useEffect } from "react";

/** True while the user is typing, so a bare letter shortcut cannot eat a keystroke. */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export type Hotkey = {
  /** Compared case-insensitively against `event.key`. */
  key: string;
  /** Cmd on Apple platforms, Ctrl elsewhere. There is no separate "ctrl" option: offering both is how a binding comes to fire twice. */
  mod?: boolean;
  shift?: boolean;
  /**
   * Fire even while a field has focus. Only for combinations a text field cannot
   * itself mean -- the palette's mod+K, never a bare letter.
   */
  whileTyping?: boolean;
};

/**
 * A window-level keyboard binding.
 *
 * `metaKey || ctrlKey` rather than a platform sniff. `navigator.platform` is
 * deprecated and is wrong for a Mac keyboard on a Windows host either way, and
 * accepting both costs nothing: no browser sends Meta for Ctrl or the reverse,
 * so a Mac user pressing Ctrl+K gets the palette too rather than nothing.
 *
 * Bound on `keydown` in the CAPTURE phase, because the composer stops Enter and
 * a future field could stop more; a shortcut that a page component can silently
 * swallow is a shortcut users learn not to trust.
 */
export function useHotkey(hotkey: Hotkey | null, handler: () => void) {
  useEffect(() => {
    if (!hotkey) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== hotkey.key.toLowerCase()) return;
      if (Boolean(hotkey.mod) !== (event.metaKey || event.ctrlKey)) return;
      if (Boolean(hotkey.shift) !== event.shiftKey) return;
      if (!hotkey.whileTyping && isTyping(event.target)) return;
      event.preventDefault();
      handler();
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [hotkey, handler]);
}
