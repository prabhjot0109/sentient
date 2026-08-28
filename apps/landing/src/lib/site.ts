/**
 * Single source of truth for outbound links.
 *
 * These were previously hardcoded in three components and had all drifted to a
 * repo slug that does not exist, 404ing from the nav, the footer and the closing
 * CTA at once. Import from here rather than re-typing a URL.
 */
export const GITHUB_REPO_URL = "https://github.com/prabhjot0109/sentient";

/**
 * Where "Get Started" / "Launch" goes: the console's sign-UP screen.
 *
 * Sign-up, not sign-in. Someone arriving from a marketing page is, by default,
 * a person who does not have an account yet; landing them on a password prompt
 * asks them to remember something they never set. The prebuilt AuthView carries
 * its own "already have an account? Sign in" switch, so the other direction
 * costs one click and no extra link here.
 *
 * A plain cross-origin link on purpose. The console is a separate build on a
 * separate origin with no cross-origin token handoff, which is what lets the two
 * ship independently -- do not "improve" this into a shared session.
 *
 * localhost, NOT 127.0.0.1, and that is not a slip. The repo-wide "127.0.0.1,
 * never localhost" rule is about the browser-to-uvicorn hop. Neon Auth rejects
 * http://127.0.0.1:<port> as an untrusted origin, so a console served from the IP
 * literal fails every sign-up. See apps/console/AGENTS.md.
 */
export const CONSOLE_URL = import.meta.env.VITE_CONSOLE_URL ?? "http://localhost:5175/auth/sign-up";
