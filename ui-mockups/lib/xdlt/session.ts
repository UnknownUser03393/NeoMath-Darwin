/**
 * XDLT session lifecycle + debounced incremental updates.
 *
 * Every edit bumps a revision; stale responses are discarded by revision so a
 * slow earlier compile can never overwrite a newer result. The bridge is
 * injectable so the revision/race logic is unit-testable without a server.
 */

import { xdltBridge, type XdltSessionOptions } from "./bridge";
import type { XdltCompileResult, XdltIncrementalResult } from "./types";

export interface UpdateMeta {
  revision: number;
  roundTripMs: number;
}

export interface XdltSessionHandlers {
  onCompile(result: XdltCompileResult, meta: { revision: number }): void;
  onUpdate(result: XdltIncrementalResult, meta: UpdateMeta): void;
  onError(error: unknown): void;
}

export interface XdltBridgeLike {
  createSession(
    content: string,
    options?: XdltSessionOptions,
  ): Promise<{ sessionId: string; result: XdltCompileResult }>;
  updateSession(
    sessionId: string,
    content: string,
    options?: XdltSessionOptions,
  ): Promise<{ sessionId: string; result: XdltIncrementalResult }>;
  destroySession(sessionId: string): Promise<void>;
}

export class XdltSessionManager {
  private sessionId: string | null = null;
  private revision = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private opened = false;
  private readonly debounceMs: number;
  private readonly bridge: XdltBridgeLike;

  constructor(
    private handlers: XdltSessionHandlers,
    debounceMs = 100,
    bridge: XdltBridgeLike = xdltBridge,
  ) {
    this.debounceMs = debounceMs;
    this.bridge = bridge;
  }

  get isOpen(): boolean {
    return this.opened;
  }

  get id(): string | null {
    return this.sessionId;
  }

  async open(content: string, options: XdltSessionOptions = {}): Promise<void> {
    await this.close();
    const revision = ++this.revision;
    try {
      const envelope = await this.bridge.createSession(content, options);
      this.sessionId = envelope.sessionId;
      this.opened = true;
      this.handlers.onCompile(envelope.result, { revision });
    } catch (error) {
      // Never reject: an unreachable backend must surface through onError
      // (which the UI shows as a diagnostic) instead of an unhandled
      // promise rejection from a bare `void manager.open(...)`.
      this.handlers.onError(error);
    }
  }

  edit(content: string, options: XdltSessionOptions = {}): void {
    if (!this.opened || !this.sessionId) return;
    const revision = ++this.revision;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.update(revision, content, options);
    }, this.debounceMs);
  }

  async flush(content: string, options: XdltSessionOptions = {}): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (!this.opened || !this.sessionId) return;
    const revision = ++this.revision;
    await this.update(revision, content, options);
  }

  private async update(
    revision: number,
    content: string,
    options: XdltSessionOptions,
  ): Promise<void> {
    if (!this.sessionId || revision !== this.revision) return;
    const started = now();
    try {
      const envelope = await this.bridge.updateSession(
        this.sessionId,
        content,
        options,
      );
      if (revision !== this.revision) return; // stale response discarded
      this.handlers.onUpdate(envelope.result, {
        revision,
        roundTripMs: now() - started,
      });
    } catch (error) {
      this.handlers.onError(error);
    }
  }

  async close(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.revision += 1;
    if (this.sessionId) {
      try {
        await this.bridge.destroySession(this.sessionId);
      } catch {
        // best-effort cleanup
      }
      this.sessionId = null;
      this.opened = false;
    }
  }
}

function now(): number {
  return typeof performance !== "undefined" ? performance.now() : 0;
}
