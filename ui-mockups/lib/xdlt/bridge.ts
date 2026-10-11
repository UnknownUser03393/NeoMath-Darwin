/**
 * Thin HTTP client for the XDLT bridge, reusing the same same-origin gateway
 * the MathCore runtime uses (``window.__NEOMATH_CORE_URL__`` / dev fallback).
 */
import { coreUrl } from "@/lib/runtime/CoreMathRuntime";
import type {
  XdltCompileResult,
  XdltCreateEnvelope,
  XdltUpdateEnvelope,
} from "./types";

export interface XdltSessionOptions {
  execute?: boolean;
  verify?: boolean;
  cardsDir?: string;
  layout?: Record<string, unknown>;
  values?: Record<string, unknown>;
}

const API_TIMEOUT_MS = 3_000;

async function callXdl<T>(method: string, payload?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${coreUrl()}/api/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
      signal: controller.signal,
    });
  } catch {
    // Fetch rejects on an unreachable backend (connection refused / offline).
    throw new Error("无法连接 XDLT 内核，请确认本地服务已启动");
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) throw new Error(`XDLT HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const xdltBridge = {
  async createSession(
    content: string,
    options: XdltSessionOptions = {},
  ): Promise<XdltCreateEnvelope> {
    const envelope = await callXdl<XdltCreateEnvelope>("createXdltSession", {
      content,
      execute: options.execute ?? true,
      verify: options.verify ?? true,
      cardsDir: options.cardsDir,
      layout: options.layout,
      values: options.values,
    });
    if (!envelope.ok) {
      throw new Error(envelope.error?.message ?? "create XDLT session failed");
    }
    return envelope;
  },

  async updateSession(
    sessionId: string,
    content: string,
    options: XdltSessionOptions = {},
  ): Promise<XdltUpdateEnvelope> {
    const envelope = await callXdl<XdltUpdateEnvelope>("updateXdltSession", {
      sessionId,
      content,
      execute: options.execute ?? true,
      verify: options.verify ?? true,
      values: options.values,
      layout: options.layout,
    });
    if (!envelope.ok) {
      throw new Error(envelope.error?.message ?? "update XDLT session failed");
    }
    return envelope;
  },

  async destroySession(sessionId: string): Promise<void> {
    await callXdl("destroyXdltSession", { sessionId });
  },

  async renderHtml(
    content: string,
    options: XdltSessionOptions = {},
  ): Promise<{ html: string; diagnostics: unknown[]; sourceMap: unknown[] }> {
    const envelope = await callXdl<{ ok: boolean; result: XdltCompileResult }>(
      "renderXdltHtml",
      {
        content,
        mode: "fragment",
        execute: options.execute ?? false,
        verify: options.verify ?? false,
        values: options.values,
        layout: options.layout,
      },
    );
    return {
      html: envelope.result.html,
      diagnostics: envelope.result.diagnostics,
      sourceMap: envelope.result.sourceMap,
    };
  },

  async referenceCss(): Promise<string> {
    const envelope = await callXdl<{ ok: boolean; result: { css: string } }>(
      "getXdltReferenceCss",
      {},
    );
    return envelope.result.css;
  },
};
