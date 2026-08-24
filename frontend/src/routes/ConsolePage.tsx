import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { AuditLogEntry, MemoryEntry, ModelManifestEntry, QuarantineAlert } from "../api/types";
import { Panel } from "../components/Panel";
import { StateBadge, autonomyTierToState, outcomeToState } from "../components/StateBadge";
import styles from "./ConsolePage.module.css";

type Tab = "memory" | "drift" | "models" | "audit" | "quarantine";

const TABS: { id: Tab; label: string }[] = [
  { id: "memory", label: "Working Memory" },
  { id: "drift", label: "Trajectory Drift" },
  { id: "models", label: "Model Registry" },
  { id: "audit", label: "Audit Trail" },
  { id: "quarantine", label: "Quarantine Vault" },
];

export function ConsolePage() {
  const [tab, setTab] = useState<Tab>("memory");

  return (
    <div className={styles.page}>
      <nav className={styles.navRail} aria-label="Console sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`${styles.navItem} ${tab === t.id ? styles.navItemActive : ""}`}
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "memory" && <MemoryTab />}
      {tab === "drift" && <DriftTab />}
      {tab === "models" && <ModelsTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "quarantine" && <QuarantineTab />}
    </div>
  );
}

function useErrorMessage() {
  const [error, setError] = useState<string | null>(null);
  const capture = useCallback((err: unknown, fallback: string) => setError(err instanceof ApiError ? err.message : fallback), []);
  return { error, setError, capture };
}

function MemoryTab() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { error, capture } = useErrorMessage();

  const refresh = () => {
    setLoading(true);
    api.memory().then((r) => setEntries(r.memories)).catch((e) => capture(e, "Could not load working memory.")).finally(() => setLoading(false));
  };

  useEffect(refresh, []);

  return (
    <Panel
      title={`Working memory · ${entries.length}`}
      action={
        <button type="button" className={styles.btn} onClick={() => api.consolidateMemory().then(refresh)}>
          Consolidate &amp; prune
        </button>
      }
    >
      {loading && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Loading…</p>}
      {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
      {entries.map((m) => (
        <div className={styles.card} key={m.entry_id}>
          <div className={styles.cardHead}>
            <div>
              <span className={styles.tag}>{m.category}</span>
              <span className={styles.mono} style={{ color: "var(--text-tertiary)" }}>
                {m.entry_id} · score {m.composite_score}
              </span>
              <p style={{ marginTop: 6 }}>{m.content}</p>
            </div>
            <button type="button" className={`${styles.btn} ${styles.btnDanger}`} onClick={() => api.purgeMemory(m.entry_id).then(refresh)}>
              Purge
            </button>
          </div>
        </div>
      ))}
      {!loading && entries.length === 0 && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>No working memory entries.</p>}
    </Panel>
  );
}

const DEFAULT_PLAN = [
  "Inspect P&ID diagram 101 for feed pump P-101 and valve V-204",
  "Retrieve ultrasonic wall thickness inspection findings for line L-204",
  "Calculate fluid velocity and pump flow rate",
  "Generate final refinery compliance and overhaul summary report",
];

function DriftTab() {
  const [action, setAction] = useState("");
  const [stepIndex, setStepIndex] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const { error, capture } = useErrorMessage();

  async function evaluate() {
    setLoading(true);
    try {
      const res = await fetch("/v1/mnemoshield/drift/eval", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("bastion_token")}` },
        body: JSON.stringify({ action, step_index: stepIndex }),
      });
      setResult(await res.json());
    } catch (e) {
      capture(e, "Drift evaluation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Panel title="Declared plan graph">
      <ol className={styles.mono} style={{ paddingLeft: 18, marginBottom: "var(--space-5)" }}>
        {DEFAULT_PLAN.map((step, i) => (
          <li key={i} style={{ marginBottom: 4, color: "var(--text-secondary)" }}>
            {step}
          </li>
        ))}
      </ol>

      <div className={styles.formRow}>
        <input className={styles.input} placeholder="Proposed action to test" value={action} onChange={(e) => setAction(e.target.value)} />
        <input className={styles.input} type="number" min={0} max={3} value={stepIndex} onChange={(e) => setStepIndex(Number(e.target.value))} aria-label="Expected step index" />
        <button type="button" className={styles.btn} onClick={evaluate} disabled={!action.trim() || loading}>
          {loading ? "Evaluating…" : "Evaluate drift"}
        </button>
      </div>
      {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
      {result && (
        <pre className={styles.card} style={{ fontFamily: "var(--font-mono)", fontSize: 11, overflowX: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </Panel>
  );
}

function ModelsTab() {
  const [models, setModels] = useState<ModelManifestEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ id: "", name: "", endpoint: "http://localhost:11434/v1", tag: "financial" });
  const { error, capture } = useErrorMessage();

  const refresh = () => {
    setLoading(true);
    api.models().then((r) => setModels(r.models)).catch((e) => capture(e, "Could not load the model registry.")).finally(() => setLoading(false));
  };
  useEffect(refresh, []);

  async function submitModel(e: React.FormEvent) {
    e.preventDefault();
    await api.addModel({
      id: form.id,
      name: form.name,
      endpoint: form.endpoint,
      served_model: "qwen2.5:7b",
      modality: "text",
      context_window: 32768,
      task_tags: [form.tag, "general"],
      is_default: false,
    });
    setForm({ id: "", name: "", endpoint: "http://localhost:11434/v1", tag: "financial" });
    setShowForm(false);
    refresh();
  }

  return (
    <Panel
      title={`Model registry · ${models.length}`}
      action={
        <div className={styles.toolbar}>
          <button type="button" className={styles.btn} onClick={() => setShowForm((s) => !s)}>
            + Register model
          </button>
          <button type="button" className={styles.btn} onClick={() => api.reloadManifest().then(refresh)}>
            Reload manifest
          </button>
        </div>
      }
    >
      {showForm && (
        <form onSubmit={submitModel} className={styles.formRow} style={{ marginBottom: "var(--space-4)" }}>
          <input className={styles.input} placeholder="Model ID" required value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} />
          <input className={styles.input} placeholder="Display name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className={styles.input} placeholder="Endpoint" required value={form.endpoint} onChange={(e) => setForm({ ...form, endpoint: e.target.value })} />
          <button type="submit" className={styles.btn}>
            Add to manifest
          </button>
        </form>
      )}
      {loading && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Loading…</p>}
      {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
      {models.map((m) => (
        <div className={styles.card} key={m.id}>
          <div className={styles.mono} style={{ color: "var(--text-tertiary)" }}>
            {m.id} → {m.served_model ?? m.id} · {m.modality}
          </div>
          <div style={{ fontWeight: 500, margin: "4px 0" }}>{m.name}</div>
          <div>
            {m.task_tags.map((t) => (
              <span className={styles.tag} key={t}>
                #{t}
              </span>
            ))}
          </div>
          {m.deployment_note && <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 6 }}>{m.deployment_note}</p>}
        </div>
      ))}
    </Panel>
  );
}

function AuditTab() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [chain, setChain] = useState<{ valid: boolean; checked_rows?: number; broken_at?: string } | null>(null);
  const { error, capture } = useErrorMessage();

  const refresh = () => {
    setLoading(true);
    api.auditLogs().then((r) => setLogs(r.logs)).catch((e) => capture(e, "Could not load the audit trail.")).finally(() => setLoading(false));
  };
  useEffect(refresh, []);

  return (
    <Panel
      title={`Audit trail · ${logs.length}`}
      action={
        <button type="button" className={styles.btn} onClick={() => api.verifyAuditChain().then(setChain)}>
          Verify hash chain
        </button>
      }
    >
      {chain && (
        <p className={chain.valid ? styles.chainOk : styles.chainBroken} style={{ fontSize: 12, marginBottom: "var(--space-3)" }}>
          {chain.valid ? `Chain intact — ${chain.checked_rows} rows verified.` : `Chain broken at ${chain.broken_at}.`}
        </p>
      )}
      {loading && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Loading…</p>}
      {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
      {!loading && !error && (
        <div style={{ overflowX: "auto" }}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Event</th>
                <th>User</th>
                <th>Action</th>
                <th>Risk tier</th>
                <th>Outcome</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.event_id}>
                  <td className={styles.mono}>{l.event_id}</td>
                  <td className={styles.mono}>{l.user_id}</td>
                  <td>{l.action}</td>
                  <td>
                    <StateBadge state={autonomyTierToState(l.risk_tier)}>{l.risk_tier.replace(/_/g, " ")}</StateBadge>
                  </td>
                  <td>
                    <StateBadge state={outcomeToState(l.outcome)}>{l.outcome}</StateBadge>
                  </td>
                  <td className={styles.mono}>{l.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function QuarantineTab() {
  const [alerts, setAlerts] = useState<QuarantineAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const { error, capture } = useErrorMessage();

  useEffect(() => {
    api.quarantineAlerts().then((r) => setAlerts(r.alerts)).catch((e) => capture(e, "Could not load the quarantine vault.")).finally(() => setLoading(false));
  }, []);

  return (
    <Panel title={`Quarantine vault · ${alerts.length}`}>
      {loading && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Loading…</p>}
      {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
      {!loading && !error && alerts.length === 0 && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Nothing quarantined.</p>}
      {alerts.map((a) => (
        <div className={styles.card} key={a.item_id}>
          <div className={styles.cardHead}>
            <span className={styles.mono}>
              {a.item_id} — {a.source} (p.{a.page})
            </span>
            <span className={styles.mono} style={{ color: "var(--text-tertiary)" }}>
              {a.quarantined_at}
            </span>
          </div>
          <div className={styles.trace}>{a.trace}</div>
        </div>
      ))}
    </Panel>
  );
}
