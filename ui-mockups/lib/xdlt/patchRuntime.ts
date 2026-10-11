/**
 * Minimal DOM patch runtime for the XDLT RenderPatch protocol.
 *
 * Applies ``replace`` / ``remove`` / ``insert`` / ``replace-document`` patches
 * straight against the preview DOM (no virtual DOM, no reconciliation). Target
 * lookup is by stable ``data-xdlt-id`` / ``data-xdlt-render-id``. Patches are
 * applied atomically: any failure restores the previous HTML and falls back to a
 * full render, so the preview never sits half-updated.
 */

import type { XdltHtmlPatch } from "./types";

export interface XdltDom {
  parseHtml(html: string): Node[];
}

const browserDom: XdltDom = {
  parseHtml(html: string): Node[] {
    const template = document.createElement("template");
    template.innerHTML = html;
    return Array.from(template.content.childNodes);
  },
};

export interface ApplyResult {
  ok: boolean;
  fallback: boolean;
  reason?: string;
}

export interface ApplyOptions {
  /** Full document HTML used to recover after a failed patch. */
  fullHtml?: string;
  onFallback?: (reason: string) => void;
}

const targetSelector = (renderId: string) =>
  `[data-xdlt-id="${escapeCssValue(renderId)}"],` +
  `[data-xdlt-render-id="${escapeCssValue(renderId)}"]`;

function escapeCssValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function findTarget(root: Element, renderId: string | undefined): Element | null {
  if (!renderId) return null;
  const found = root.querySelectorAll(targetSelector(renderId));
  return found.length === 1 ? found[0] : null;
}

function applyOnePatch(root: Element, patch: XdltHtmlPatch, dom: XdltDom): boolean {
  if (patch.op === "replace-document") {
    if (!patch.html) return false;
    root.innerHTML = patch.html;
    return true;
  }
  if (patch.op === "replace") {
    const target = findTarget(root, patch.renderId);
    if (!target) return false;
    const nodes = dom.parseHtml(patch.html ?? "");
    if (nodes.length === 0) return false;
    target.replaceWith(...nodes);
    return true;
  }
  if (patch.op === "remove") {
    const target = findTarget(root, patch.renderId);
    if (!target) return false;
    target.remove();
    return true;
  }
  if (patch.op === "insert") {
    const parent = findTarget(root, patch.parentRenderId);
    if (!parent) return false;
    const nodes = dom.parseHtml(patch.html ?? "");
    if (nodes.length === 0) return false;
    const children = Array.from(parent.children);
    const index = patch.index ?? -1;
    if (index < 0 || index > children.length) return false;
    if (index === children.length) {
      nodes.forEach((node) => parent.appendChild(node));
    } else {
      const reference = children[index];
      nodes.forEach((node) => parent.insertBefore(node, reference));
    }
    return true;
  }
  return false;
}

export function applyXdltPatch(
  root: Element,
  patch: XdltHtmlPatch,
  dom: XdltDom = browserDom,
): boolean {
  return applyOnePatch(root, patch, dom);
}

export function applyXdltPatches(
  root: Element,
  patches: XdltHtmlPatch[],
  options: ApplyOptions = {},
  dom: XdltDom = browserDom,
): ApplyResult {
  const saved = root.innerHTML;
  try {
    for (const patch of patches) {
      if (!applyOnePatch(root, patch, dom)) {
        throw new Error(
          `xdlt patch failed: ${patch.op} ${patch.renderId ?? patch.parentRenderId ?? ""}`,
        );
      }
    }
    return { ok: true, fallback: false };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    // Atomic restore: put back the pre-patch DOM, then full render.
    root.innerHTML = saved;
    if (options.fullHtml) root.innerHTML = options.fullHtml;
    if (options.onFallback) options.onFallback(reason);
    return { ok: false, fallback: true, reason };
  }
}

