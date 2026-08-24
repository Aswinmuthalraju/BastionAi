import { useState } from "react";
import type { ProvenanceStage } from "../api/types";
import styles from "./ProvenanceSpine.module.css";

const STAGE_LABEL: Record<string, string> = {
  screened: "Screen",
  drift_checked: "Drift",
  scored: "Score",
  routed: "Route",
  retrieved: "Retrieve",
  executed: "Execute",
};

function markerState(stage: ProvenanceStage): string {
  const s = stage.status;
  if (["blocked", "interlock", "dual_approval_required"].includes(s)) return "interlock";
  if (["drifted", "caution", "human_approval_required"].includes(s)) return "caution";
  if (["clear", "on_track", "ok", "verified", "auto_execute"].includes(s)) return "verified";
  if (["execute_and_verify"].includes(s)) return "nominal";
  return "nominal";
}

function summarize(stage: ProvenanceStage): string {
  const d = stage.detail as Record<string, any>;
  switch (stage.stage) {
    case "screened":
      return d.is_malicious
        ? `blocked · detected by ${d.detected_by}`
        : `clear · ml ${d.ml_rail?.confidence_score ?? "—"}${d.ml_rail?.degraded ? " (degraded)" : ""}`;
    case "drift_checked":
      return `${d.is_drifted ? "drifted" : "on track"} · score ${d.drift_score} (threshold ${d.drift_threshold})`;
    case "scored":
      return `risk ${d.total_risk_score}/10 · ${String(d.autonomy_tier).replace(/_/g, " ")}`;
    case "routed":
      return `${d.model_id} → ${d.served_model} · tag=${d.tag}`;
    case "retrieved":
      return `${d.chunk_count} chunk${d.chunk_count === 1 ? "" : "s"}`;
    case "executed":
      return d.tool
        ? `tool: ${d.tool}`
        : `${d.latency_s ?? "—"}s · ${d.completion_tokens ?? "—"} tok · ${d.served_model ?? ""}`;
    default:
      return stage.status;
  }
}

function StageRow({ stage }: { stage: ProvenanceStage }) {
  const [open, setOpen] = useState(false);
  const state = markerState(stage);

  return (
    <li className={styles.stage}>
      <span className={`${styles.marker} ${styles[state]}`} aria-hidden="true" />
      <button
        type="button"
        className={styles.row}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className={styles.stageName}>{STAGE_LABEL[stage.stage] ?? stage.stage}</span>
        <span className={styles.summary}>{summarize(stage)}</span>
        <span className={styles.toggle} aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open && <pre className={styles.detail}>{JSON.stringify(stage.detail, null, 2)}</pre>}
    </li>
  );
}

export function ProvenanceSpine({ stages }: { stages: ProvenanceStage[] }) {
  if (stages.length === 0) return null;
  return (
    <ol className={styles.spine} aria-label="Request provenance">
      {stages.map((s, i) => (
        <StageRow key={`${s.stage}-${i}`} stage={s} />
      ))}
    </ol>
  );
}
