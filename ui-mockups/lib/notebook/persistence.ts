import type { NotebookDocument } from "./types";
import { coreUrl } from "@/lib/runtime/CoreMathRuntime";

/** One notebook file in the workspace (``<name>.nm`` on disk). */
export interface NotebookFileMeta {
  name: string;
  fileName: string;
  title: string;
  updatedAt?: number;
}

/** One XDLT document in the workspace (``<name>.xdlt`` on disk). */
export interface XdltFileMeta {
  name: string;
  fileName: string;
  title: string;
  updatedAt?: number;
}

export interface WorkspaceState {
  files: NotebookFileMeta[];
  seeded: boolean;
}

export interface XdltWorkspaceState {
  files: XdltFileMeta[];
  seeded: boolean;
}

interface ApiResult<T> {
  ok: boolean;
  result?: T;
  error?: { type?: string; code?: string; message?: string };
}

const LAST_FILE_KEY = "neomath:last-file:v1";
const LAST_XDLT_FILE_KEY = "neomath:last-xdlt-file:v1";
const API_TIMEOUT_MS = 3_000;

async function call<T>(method: string, payload?: unknown): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const response = await fetch(`${coreUrl()}/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
      signal: controller.signal,
    });
    if (!response.ok) {
      return { ok: false, error: { message: `HTTP ${response.status}` } };
    }
    return (await response.json()) as ApiResult<T>;
  } catch {
    return { ok: false, error: { message: "offline" } };
  } finally {
    clearTimeout(timeout);
  }
}

/** List workspace files; null when the backend is unreachable. */
export async function listNotebooks(): Promise<WorkspaceState | null> {
  const result = await call<WorkspaceState>("listNotebooks");
  return result.ok && result.result ? result.result : null;
}

export async function loadNotebookFile(
  fileName: string,
): Promise<NotebookDocument | null> {
  const result = await call<{ document: NotebookDocument }>("loadNotebook", {
    name: fileName,
  });
  const document = result.result?.document;
  return document && Array.isArray(document.cells) ? document : null;
}

export async function saveNotebookFile(
  fileName: string,
  document: NotebookDocument,
): Promise<boolean> {
  const result = await call<{ fileName: string }>("saveNotebook", {
    name: fileName,
    document,
  });
  return result.ok;
}

export async function renameNotebookFile(
  from: string,
  to: string,
): Promise<{ ok: boolean; fileName?: string; message?: string }> {
  const result = await call<{ fileName: string }>("renameNotebook", {
    from,
    to,
  });
  return {
    ok: result.ok,
    fileName: result.result?.fileName,
    message: result.error?.message,
  };
}

export async function seedNotebooks(): Promise<void> {
  await call("seedNotebooks");
}

/** List XDLT workspace files; null when the backend is unreachable. */
export async function listXdltDocuments(): Promise<XdltWorkspaceState | null> {
  const result = await call<XdltWorkspaceState>("listXdltDocuments");
  return result.ok && result.result ? result.result : null;
}

export async function loadXdltDocument(
  fileName: string,
): Promise<string | null> {
  const result = await call<{ source: string }>("loadXdltDocument", {
    name: fileName,
  });
  return result.result?.source ?? null;
}

export async function saveXdltDocument(
  fileName: string,
  source: string,
): Promise<boolean> {
  const result = await call<{ fileName: string }>("saveXdltDocument", {
    name: fileName,
    source,
  });
  return result.ok;
}

export async function renameXdltDocument(
  from: string,
  to: string,
): Promise<{ ok: boolean; fileName?: string; message?: string }> {
  const result = await call<{ fileName: string }>("renameXdltDocument", {
    from,
    to,
  });
  return {
    ok: result.ok,
    fileName: result.result?.fileName,
    message: result.error?.message,
  };
}

export async function seedXdltDocuments(): Promise<void> {
  await call("seedXdltDocuments");
}

/** Remember which file to reopen on next launch. */
export function rememberLastFile(fileName: string | null): void {
  try {
    if (fileName === null) {
      window.localStorage.removeItem(LAST_FILE_KEY);
    } else {
      window.localStorage.setItem(LAST_FILE_KEY, fileName);
    }
  } catch {
    /* ignore — in-memory only */
  }
}

export function lastFile(): string | null {
  try {
    return window.localStorage.getItem(LAST_FILE_KEY);
  } catch {
    return null;
  }
}

/** Remember which XDLT document to reopen on next launch. */
export function rememberLastXdltFile(fileName: string | null): void {
  try {
    if (fileName === null) {
      window.localStorage.removeItem(LAST_XDLT_FILE_KEY);
    } else {
      window.localStorage.setItem(LAST_XDLT_FILE_KEY, fileName);
    }
  } catch {
    /* ignore — in-memory only */
  }
}

export function lastXdltFile(): string | null {
  try {
    return window.localStorage.getItem(LAST_XDLT_FILE_KEY);
  } catch {
    return null;
  }
}
