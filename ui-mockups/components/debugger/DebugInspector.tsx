"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  CheckCircle2,
  CircleDashed,
  FlaskConical,
  PauseCircle,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useNotebook } from "@/lib/notebook/commands";
import {
  analysisFromResult,
  isMathCell,
  type ProbeResult,
} from "@/lib/notebook/types";

/** 光流轨道：把「执行前 → 执行后」的状态转移用一条流动的光线表达。 */
function StateFlowBeam({ active, fault }: { active: boolean; fault: boolean }) {
  const reduce = useReducedMotion();
  return (
    <div
      className={`state-flow-track ${active ? "active" : ""} ${fault ? "fault" : ""}`}
      aria-hidden="true"
    >
      <motion.span
        className={`state-flow-orb ${fault ? "fault" : ""}`}
        initial={false}
        animate={
          fault
            ? { top: "calc(100% - 8px)" }
            : reduce || !active
            ? { top: "0%" }
            : { top: ["0%", "calc(100% - 8px)"] }
        }
        transition={
          fault || reduce || !active
            ? { duration: 0 }
            : {
                repeat: Infinity,
                repeatType: "reverse",
                duration: 1.1,
                ease: "easeInOut",
              }
        }
      />
    </div>
  );
}

function InspectorRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="inspector-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function DebugInspector() {
  const { state, evaluateProbe, applyWitnessProbe } = useNotebook();
  const mathSteps = useMemo(
    () => state.document.cells.filter(isMathCell),
    [state.document.cells],
  );
  const selected = mathSteps.find((cell) => cell.id === state.selectedCellId) ?? mathSteps[0];
  const stepIndex = selected ? mathSteps.findIndex((cell) => cell.id === selected.id) : -1;
  const previous = stepIndex > 0 ? mathSteps[stepIndex - 1] : undefined;
  const analysis = analysisFromResult(selected?.result);
  const resultType = selected?.result?.type;
  const diagnostic = resultType === "diagnostic" ? selected.result : null;
  const stateFault = resultType === "diagnostic" || resultType === "unsupported";
  const flowActive = resultType === "math" || resultType === "equivalence";
  const [probeValue, setProbeValue] = useState("");
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null);
  const [probeBusy, setProbeBusy] = useState(false);

  useEffect(() => {
    setProbeResult(null);
    if (diagnostic?.witness.value.startsWith("x =")) {
      setProbeValue(diagnostic.witness.value.replace(/^x\s*=\s*/, ""));
    }
  }, [selected?.id, diagnostic?.witness.value]);

  const runProbe = async () => {
    if (!probeValue.trim()) return;
    setProbeBusy(true);
    try {
      setProbeResult(await evaluateProbe(probeValue));
    } finally {
      setProbeBusy(false);
    }
  };

  const runWitnessProbe = async () => {
    if (!diagnostic) return;
    setProbeBusy(true);
    try {
      const applied = await applyWitnessProbe(diagnostic.witness.value);
      if (applied.ok) {
        setProbeValue(applied.value);
        setProbeResult(applied.result);
      }
    } finally {
      setProbeBusy(false);
    }
  };

  const stateIcon =
    selected?.executionState === "error" ? (
      <PauseCircle size={16} />
    ) : selected?.executionState === "success" ? (
      <CheckCircle2 size={16} />
    ) : (
      <CircleDashed size={16} />
    );

  return (
    <aside className="debug-inspector" data-demo-id="debug-inspector" aria-label="调试器">
      <div className="inspector-titlebar">
        <span>调试器</span>
        <span className="inspector-step">STEP {Math.max(1, stepIndex + 1)} / {mathSteps.length}</span>
      </div>

      <section className={`inspector-status ${diagnostic ? "fault" : ""}`}>
        {stateIcon}
        <div>
          <span>当前状态</span>
          <strong>
            {diagnostic
              ? "在语义分叉处暂停"
              : selected?.executionState === "success"
                ? "此步保持等价"
                : "等待验证"}
          </strong>
        </div>
      </section>

      <section className="inspector-section">
        <h3>状态快照</h3>
        <div className="state-transition">
          <StateFlowBeam
            key={`${selected?.id ?? "empty"}:${resultType ?? "idle"}`}
            active={flowActive}
            fault={stateFault}
          />
          <div className="state-transition-values">
            <div className="state-snapshot before">
              <code>{previous?.source || "程序入口"}</code>
            </div>
            <div className={`state-snapshot after ${stateFault ? "fault" : ""} ${diagnostic ? "changed" : ""}`}>
              <code>{selected?.source || "—"}</code>
            </div>
          </div>
        </div>
        {analysis && (
          <div className="inspector-table">
            <InspectorRow label="解集" value={analysis.solutionSet} />
            <InspectorRow label="定义域" value={analysis.domain} />
            <InspectorRow label="判定" value={analysis.status} />
            <InspectorRow label="可信级别" value={analysis.trustLevel} />
          </div>
        )}
      </section>

      {diagnostic && (
        <section className="inspector-section fault-section">
          <h3><XCircle size={14} /> 断点原因</h3>
          <strong className="fault-name">{diagnostic.code} · {diagnostic.title}</strong>
          <p>{diagnostic.summary}</p>
          <div className="solution-diff">
            <div><span>此前</span><strong>{diagnostic.previousSet}</strong></div>
            <div><span>此后</span><strong>{diagnostic.currentSet}</strong></div>
          </div>
          <div className="witness-card">
            <span className="witness-label"><FlaskConical size={13} /> 自动反例</span>
            <strong>{diagnostic.witness.value}</strong>
            <p>{diagnostic.witness.original}</p>
            <p className="witness-failed">{diagnostic.witness.transformed}</p>
            <button
              type="button"
              className="witness-apply"
              onClick={() => void runWitnessProbe()}
              disabled={probeBusy || diagnostic.witness.value === "—"}
              title="把 Witness 一键写入 Probe 并代回"
            >
              <FlaskConical size={13} />
              {probeBusy ? "代回中…" : "一键代回 Witness"}
            </button>
          </div>
        </section>
      )}

      <section className="inspector-section probe-section">
        <h3><FlaskConical size={14} /> Probe</h3>
        <div className="inspector-probe-row">
          <span>x =</span>
          <input
            value={probeValue}
            onChange={(event) => setProbeValue(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && void runProbe()}
            placeholder="0 或 1/2"
            aria-label="Probe 值"
          />
          <button onClick={() => void runProbe()} disabled={!probeValue.trim() || probeBusy}>
            {probeBusy ? "…" : "验证"}
          </button>
        </div>
        {probeResult && (
          <div className="inspector-probe-result">
            <span><ShieldCheck size={13} /> x = {probeResult.value}</span>
            <strong>{probeResult.previousEval}</strong>
            <strong className={probeResult.currentHolds === false ? "failed" : ""}>
              {probeResult.currentEval}
            </strong>
          </div>
        )}
      </section>
    </aside>
  );
}
