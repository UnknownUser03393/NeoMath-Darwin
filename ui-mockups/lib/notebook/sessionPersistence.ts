/** Persist the open tab set across page reloads.

    Only file *references* are saved (never full documents) — the content is
    re-loaded from the backend on restore. Unsaved canvases are stored as
    `fileName: null`, so a blank notebook / demo xdlt canvas is recreated. */

export interface SessionTabRef {
  kind: "notebook" | "xdlt";
  /** On-disk name, or null for an unsaved canvas. */
  fileName: string | null;
}

export interface SavedSession {
  tabs: SessionTabRef[];
  /** Index into `tabs` of the active tab. */
  activeTabIndex: number;
}

const SESSION_KEY = "neomath:session:v1";

export function saveSession(session: SavedSession | null): void {
  try {
    if (session === null || session.tabs.length === 0) {
      window.localStorage.removeItem(SESSION_KEY);
      return;
    }
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* ignore — in-memory only */
  }
}

export function loadSession(): SavedSession | null {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SavedSession;
    if (!Array.isArray(parsed.tabs) || parsed.tabs.length === 0) return null;
    const tabs = parsed.tabs
      .filter(
        (t): t is SessionTabRef =>
          (t.kind === "notebook" || t.kind === "xdlt") &&
          (typeof t.fileName === "string" || t.fileName === null),
      )
      .slice(0, 32);
    if (tabs.length === 0) return null;
    return {
      tabs,
      activeTabIndex: Math.min(
        Math.max(0, parsed.activeTabIndex ?? 0),
        tabs.length - 1,
      ),
    };
  } catch {
    return null;
  }
}
