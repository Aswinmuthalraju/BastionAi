import { useRef, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import type { ChatResponse } from "../api/types";
import { ProvenanceSpine } from "../components/ProvenanceSpine";
import { RiskMeterRow } from "../components/RiskMeter";
import { useWorkbench, type ChatTurn } from "../context/WorkbenchContext";
import { renderRichText } from "../lib/richText";
import styles from "./WorkbenchPage.module.css";

function newId() {
  return `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function WorkbenchPage() {
  const {
    turns,
    input,
    pendingImage,
    uploadError,
    setInput,
    setPendingImage,
    setUploadError,
    runTurn,
    clearTurns,
    removeTurn,
    addTurn,
  } = useWorkbench();
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const prompt = input.trim();
    if (!prompt) return;

    const id = newId();
    const imageDocId = pendingImage?.docId;
    addTurn({ id, prompt, imageDocId, imageName: pendingImage?.filename, pending: true });
    setInput("");
    setPendingImage(null);
    void runTurn(id, prompt, imageDocId);
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploadError(null);
    try {
      const result = await api.uploadDocument(file);
      if (result.status === "quarantined") {
        setUploadError(`"${file.name}" was quarantined — it matched the injection screen and was not indexed. See Console → Quarantine.`);
        return;
      }
      setPendingImage({ docId: result.doc_id, filename: file.name });
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.thread} role="log" aria-label="Conversation">
        {turns.length > 0 && (
          <div className={styles.threadHeader}>
            <button type="button" className={styles.clearBtn} onClick={clearTurns}>
              Clear thread
            </button>
          </div>
        )}

        {turns.length === 0 && (
          <div className={styles.empty}>
            <svg className={styles.emptyMark} viewBox="0 0 32 32" aria-hidden="true">
              <path d="M16 5 L26 9 V16 C26 22 21.5 26.5 16 28 C10.5 26.5 6 22 6 16 V9 Z" fill="none" stroke="var(--text-tertiary)" strokeWidth="2" />
            </svg>
            <p>Ask an engineering question, request a calculation, or attach a diagram. Every response carries the pipeline it actually ran through.</p>
          </div>
        )}

        {turns.map((turn) => (
          <TurnView key={turn.id} turn={turn} onApprove={() => runTurn(turn.id, turn.prompt, turn.imageDocId, true)} onReject={() => removeTurn(turn.id)} />
        ))}
      </div>

      <form className={styles.composer} onSubmit={handleSubmit}>
        {pendingImage && (
          <span className={styles.attachChip}>
            📎 {pendingImage.filename}
            <button type="button" onClick={() => setPendingImage(null)} aria-label="Remove attachment">
              ×
            </button>
          </span>
        )}
        {uploadError && <div className={styles.errorBanner} role="alert">{uploadError}</div>}

        <div className={styles.inputRow}>
          <input ref={fileInputRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.txt" className="visually-hidden" onChange={handleFileSelected} aria-hidden="true" tabIndex={-1} />
          <button type="button" className={styles.iconBtn} onClick={() => fileInputRef.current?.click()} aria-label="Attach a diagram or document">
            📎
          </button>
          <label htmlFor="prompt-input" className="visually-hidden">
            Engineering query or instruction
          </label>
          <input
            id="prompt-input"
            className={styles.textInput}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter an engineering query or instruction…"
          />
          <button type="submit" className={styles.sendBtn} disabled={!input.trim()}>
            Execute
          </button>
        </div>
      </form>
    </div>
  );
}

function TurnView({ turn, onApprove, onReject }: { turn: ChatTurn; onApprove: () => void; onReject: () => void }) {
  return (
    <>
      <div className={`${styles.msg} ${styles.msgUser}`}>
        <div className={styles.bubbleUser}>
          <div className={styles.roleLabel}>Operator{turn.imageName ? ` · attached ${turn.imageName}` : ""}</div>
          {turn.prompt}
        </div>
      </div>

      <div className={`${styles.msg} ${styles.msgAssistant}`}>
        {turn.pending && (
          <div className={styles.pendingCard}>
            <span className={styles.spinner} aria-hidden="true" />
            Screening, routing, and executing against the live model — this can take several seconds on local hardware.
          </div>
        )}

        {turn.error && (
          <div className={styles.blockedCard} role="alert">
            {turn.error}
          </div>
        )}

        {turn.response && <ResponseView response={turn.response} onApprove={onApprove} onReject={onReject} />}
      </div>
    </>
  );
}

function ResponseView({ response, onApprove, onReject }: { response: ChatResponse; onApprove: () => void; onReject: () => void }) {
  if (response.status === "approval_required") {
    const risk = response.risk_analysis!;
    return (
      <div className={styles.holdCard}>
        <div className={styles.holdTitle}>⏸ Autonomy hold — {response.passport?.autonomy_required.replace(/_/g, " ")}</div>
        <RiskMeterRow label="Sensitivity" value={risk.sensitivity} max={5} />
        <RiskMeterRow label="Tool danger" value={risk.tool_danger} max={5} />
        <RiskMeterRow label="Reversibility" value={risk.reversibility} max={5} />
        <ul className={styles.riskFactors}>
          {risk.risk_factors.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
        <div className={styles.holdActions}>
          <button type="button" className={styles.btnReject} onClick={onReject}>
            Reject and abort
          </button>
          <button type="button" className={styles.btnApprove} onClick={onApprove}>
            Approve action
          </button>
        </div>
      </div>
    );
  }

  if (response.status === "quarantined_and_blocked") {
    return (
      <div className={styles.blockedCard}>
        Execution blocked — this request matched the injection screen and was quarantined.
        <div className={styles.blockedTrace}>{response.trace_message}</div>
      </div>
    );
  }

  if (response.status === "rejected" || response.status === "error") {
    return <div className={styles.blockedCard}>{response.reason || "The request could not be completed."}</div>;
  }

  return (
    <div>
      <div className={styles.responseText}>{renderRichText(response.agent_response ?? "")}</div>

      {!!response.evidence_citations?.length && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Evidence · {response.evidence_citations.length} source{response.evidence_citations.length === 1 ? "" : "s"}</div>
          {response.evidence_citations.map((c) => (
            <div className={styles.citation} key={c.citation_id}>
              <div className={styles.citationHead}>
                <span>{c.source_doc} · p.{c.page_number}</span>
                <span>similarity {c.similarity.toFixed(2)}</span>
              </div>
              <div className={styles.citationSnippet}>"{c.snippet}"</div>
            </div>
          ))}
        </div>
      )}

      {!!response.provenance?.length && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Provenance</div>
          <ProvenanceSpine stages={response.provenance} />
        </div>
      )}
    </div>
  );
}
