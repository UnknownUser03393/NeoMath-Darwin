"use client";

import { useEffect, useState } from "react";
import { useNotebook } from "@/lib/notebook/commands";
import {
  analysisFromResult,
  isMathCell,
  type ProbeResult,
} from "@/lib/notebook/types";
import { DEMO_CATALOG } from "@/lib/notebook/demos";

/** Live variables / watch panel for the selected math cell. */
export function VariablesPanel() {
  const { state, evaluateProbe } = useNotebook();
  const selected = state.document.cells.find(
    (cell) => cell.id === state.selectedCellId,
  );
  const analysis =
    selected && isMathCell(selected)
      ? analysisFromResult(selected.result)
      : null;
  const [probeValue, setProbeValue] = useState("");
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null);
  const [probeBusy, setProbeBusy] = useState(false);

  useEffect(() => {
    queueMicrotask(() => setProbeResult(null));
  }, [state.selectedCellId, state.document.id]);

  // Prefill witness when diagnostic is selected
  useEffect(() => {
    if (
      selected &&
      isMathCell(selected) &&
      selected.result?.type === "diagnostic" &&
      selected.result.witness.value.startsWith("x =")
    ) {
      const witnessValue = selected.result.witness.value.replace(/^x\s*=\s*/, "");
      queueMicrotask(() => setProbeValue(witnessValue));
    }
  }, [selected]);

  const runProbe = async () => {
    setProbeBusy(true);
    try {
      const result = await evaluateProbe(probeValue);
      setProbeResult(result);
    } finally {
      setProbeBusy(false);
    }
  };

  return (
    <div className="panel-body" data-panel="variables">
      <div className="panel-section">
        <div className="panel-subheading">当前步骤</div>
        {!selected || !isMathCell(selected) ? (
          <p className="panel-empty">选中一个推导步骤以查看解集与定义域。</p>
        ) : !analysis ? (
          <p className="panel-empty">运行后可在此查看解集、定义域与可信级别。</p>
        ) : (
          <ul className="panel-kv" aria-label="单元格分析">
            <li>
              <span>状态</span>
              <strong>{analysis.status}</strong>
            </li>
            <li>
              <span>解集</span>
              <strong className="mono">{analysis.solutionSet}</strong>
            </li>
            <li>
              <span>定义域</span>
              <strong className="mono">{analysis.domain}</strong>
            </li>
            <li>
              <span>可信级别</span>
              <strong>{analysis.trustLevel}</strong>
            </li>
            <li>
              <span>耗时</span>
              <strong>{analysis.duration}</strong>
            </li>
          </ul>
        )}
      </div>

      <div className="panel-section">
        <div className="panel-subheading">手动 Probe</div>
        <p className="panel-hint">
          输入有理数，代回当前推导前缀，检查在分叉前后是否成立。
        </p>
        <div className="probe-row">
          <label className="sr-only" htmlFor="manual-probe">
            Probe 值
          </label>
          <span className="probe-prefix">x =</span>
          <input
            id="manual-probe"
            className="panel-input compact"
            inputMode="decimal"
            placeholder="0 或 1/2"
            value={probeValue}
            onChange={(event) => setProbeValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void runProbe();
            }}
          />
          <button
            type="button"
            className="panel-button"
            onClick={() => void runProbe()}
            disabled={probeBusy || !probeValue.trim()}
          >
            {probeBusy ? "…" : "检验"}
          </button>
        </div>
        {probeResult && (
          <div className="probe-result" role="status">
            <div className="probe-result-value">x = {probeResult.value}</div>
            <div className="probe-checks">
              <div>
                <span>此前</span>
                <strong>{probeResult.previousEval}</strong>
              </div>
              <div className={probeResult.currentHolds === false ? "failed" : ""}>
                <span>此后</span>
                <strong>{probeResult.currentEval}</strong>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function HelpPanel() {
  return (
    <div className="panel-body" data-panel="help">
      <div className="panel-section">
        <div className="panel-subheading">这是什么</div>
        <p className="panel-empty">
          NeoMath 把代数推导当作程序运行：比较相邻步骤的解集与定义域，并用具体数值（Witness）说明哪里丢根、增根或扩大了定义域。
        </p>
      </div>
      <div className="panel-section">
        <div className="panel-subheading">快捷键</div>
        <ul className="panel-kv compact">
          <li>
            <span>Ctrl + Enter</span>
            <strong>验证当前步骤</strong>
          </li>
          <li>
            <span>全部运行</span>
            <strong>继续到第一处分叉</strong>
          </li>
          <li>
            <span>Ctrl + S</span>
            <strong>保存到本机</strong>
          </li>
          <li>
            <span>Ctrl + + / −</span>
            <strong>页面缩放（WebView 原生）</strong>
          </li>
          <li>
            <span>Ctrl + 0</span>
            <strong>重置缩放</strong>
          </li>
          <li>
            <span>Ctrl + 滚轮</span>
            <strong>页面缩放</strong>
          </li>
        </ul>
      </div>
      <div className="panel-section">
        <div className="panel-subheading">四个演示</div>
        <ul className="panel-list">
          {DEMO_CATALOG.map((demo) => (
            <li key={demo.id}>
              <span className="panel-mono">{demo.prefix}</span>
              <span>
                <strong>{demo.fileName}</strong>
                <br />
                <span className="panel-muted">{demo.blurb}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="panel-section">
        <div className="panel-subheading">如何变形</div>
        <p className="panel-empty">
          在工具栏里点算子；除法/乘法在输入框填数学式（如
          <code className="mono">10</code> 或 <code className="mono">x</code>
          ）。
        </p>
      </div>
      <div className="panel-section">
        <div className="panel-subheading">支持范围（v1）</div>
        <p className="panel-empty">
          单变量 x、精确有理数、一次/有理根二次方程、简单分式与线性根式。超出范围会明确返回「暂时无法验证」，而不是猜答案。
        </p>
      </div>
    </div>
  );
}

export function SettingsPanel() {
  const { kernelStatus, kernelUrl, refreshKernel, reset, saveNow } =
    useNotebook();
  const statusLabel =
    kernelStatus === "core"
      ? "MathCore 已连接"
      : kernelStatus === "checking"
        ? "正在检测内核…"
        : "离线演示模式";

  return (
    <div className="panel-body" data-panel="settings">
      <div className="panel-section">
        <div className="panel-subheading">内核</div>
        <ul className="panel-kv">
          <li>
            <span>状态</span>
            <strong
              className={
                kernelStatus === "core"
                  ? "status-ok"
                  : kernelStatus === "offline"
                    ? "status-warn"
                    : ""
              }
            >
              {statusLabel}
            </strong>
          </li>
          <li>
            <span>地址</span>
            <strong className="mono">{kernelUrl}</strong>
          </li>
        </ul>
        <button
          type="button"
          className="panel-button block"
          onClick={() => void refreshKernel()}
        >
          重新检测连接
        </button>
        <p className="panel-hint">
          桌面应用内嵌时自动连接本机内核。开发联调可运行{" "}
          <code className="mono">python -m neomath --serve</code>。
        </p>
      </div>
      <div className="panel-section">
        <div className="panel-subheading">调试会话</div>
        <button type="button" className="panel-button block" onClick={saveNow}>
          立即保存
        </button>
        <button type="button" className="panel-button block ghost" onClick={reset}>
          重置当前演示
        </button>
        <p className="panel-hint">文档保存在浏览器本地存储，不会上传。</p>
      </div>
    </div>
  );
}

// Back-compat names used by older imports/tests
export const VariablesPanelSkeleton = VariablesPanel;
export const HelpPanelSkeleton = HelpPanel;
export const SettingsPanelSkeleton = SettingsPanel;
export function SearchPanelSkeleton() {
  return null;
}
