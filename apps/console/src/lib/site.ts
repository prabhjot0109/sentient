/**
 * Outbound links, in one place.
 *
 * Landing has the same file for the same reason: these were hardcoded across
 * three of its components and had all drifted to a repo slug that did not
 * exist, 404ing from three places at once.
 *
 * They point at files in the repository rather than at a docs site, because
 * that is where they actually live and a link to a page nobody has built is
 * worse than no link.
 */
export const GITHUB_REPO_URL = "https://github.com/prabhjot0109/sentient";
export const ISSUES_URL = `${GITHUB_REPO_URL}/issues/new/choose`;
export const PRIVACY_URL = `${GITHUB_REPO_URL}/blob/main/PRIVACY.md`;
export const TERMS_URL = `${GITHUB_REPO_URL}/blob/main/TERMS.md`;
