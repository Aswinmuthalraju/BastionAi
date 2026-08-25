import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { DocumentRecord } from "../api/types";
import { Panel } from "../components/Panel";
import { StateBadge, type MachineState } from "../components/StateBadge";
import styles from "./DocumentsPage.module.css";

function statusToState(status: string): MachineState {
  if (status === "indexed") return "verified";
  if (status === "quarantined") return "interlock";
  if (status === "failed") return "interlock";
  return "caution";
}

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listDocuments();
      setDocuments(res.documents);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the document library.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadNotice(null);
    try {
      const result = await api.uploadDocument(file);
      if (result.status === "quarantined") {
        setUploadNotice(`"${file.name}" was quarantined at ingestion — it matched the injection screen and was not indexed.`);
      } else if (result.status === "failed") {
        setUploadNotice(`"${file.name}" failed to process: ${result.error}`);
      } else {
        setUploadNotice(`"${file.name}" indexed — ${result.indexed_chunks} page(s) searchable.`);
      }
      await refresh();
      setSelectedId(result.doc_id);
    } catch (err) {
      setUploadNotice(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(docId: string, filename: string, e?: React.MouseEvent) {
    if (e) e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      await api.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      if (selectedId === docId) setSelectedId(null);
      setUploadNotice(`"${filename}" was deleted successfully.`);
    } catch (err) {
      setUploadNotice(err instanceof ApiError ? err.message : "Could not delete document.");
    }
  }

  const selected = documents.find((d) => d.doc_id === selectedId) ?? null;

  return (
    <div className={styles.page}>
      <div>
        <Panel title="Upload">
          <div
            className={`${styles.dropZone} ${dragOver ? styles.dropZoneActive : ""}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              void handleFiles(e.dataTransfer.files);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
          >
            {uploading ? "Uploading and screening…" : "Drop a PDF, image, or text file — or click to browse"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.txt"
              className="visually-hidden"
              onChange={(e) => void handleFiles(e.target.files)}
              tabIndex={-1}
              aria-hidden="true"
            />
          </div>
          {uploadNotice && <p style={{ marginTop: "var(--space-3)", fontSize: 12, color: "var(--text-secondary)" }}>{uploadNotice}</p>}
        </Panel>

        <div style={{ height: "var(--space-4)" }} />

        <Panel title={`Library · ${documents.length}`}>
          {loading && <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Loading…</p>}
          {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
          {!loading && !error && documents.length === 0 && (
            <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>No documents yet. Upload one above.</p>
          )}
          <ul className={styles.list}>
            {documents.map((doc) => (
              <li key={doc.doc_id}>
                <div className={styles.itemRow}>
                  <button
                    type="button"
                    className={`${styles.itemBtn} ${doc.doc_id === selectedId ? styles.itemBtnActive : ""}`}
                    onClick={() => setSelectedId(doc.doc_id)}
                  >
                    <div className={styles.itemName}>{doc.filename}</div>
                    <div className={styles.itemMeta}>
                      {doc.data_scope} · {doc.page_count} pg
                    </div>
                  </button>
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    onClick={(e) => void handleDelete(doc.doc_id, doc.filename, e)}
                    title="Delete document"
                    aria-label={`Delete ${doc.filename}`}
                  >
                    ×
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title={selected ? selected.filename : "Document"} bodyClassName={styles.detail}>
        {!selected && <p className={styles.empty}>Select a document from the library to view it.</p>}
        {selected && (
          <DocumentDetail
            doc={selected}
            onDelete={() => void handleDelete(selected.doc_id, selected.filename)}
          />
        )}
      </Panel>
    </div>
  );
}

function DocumentDetail({ doc, onDelete }: { doc: DocumentRecord; onDelete: () => void }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let revoke: string | null = null;
    setBlobUrl(null);
    setError(null);
    api
      .fetchDocumentBlob(doc.doc_id)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        revoke = url;
        setBlobUrl(url);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this file."));
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [doc.doc_id]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button type="button" className={styles.deleteDetailBtn} onClick={onDelete}>
          × Delete document
        </button>
      </div>

      <div className={styles.metaGrid}>
        <div>
          <div className={styles.metaLabel}>Status</div>
          <StateBadge state={statusToState(doc.status)}>{doc.status}</StateBadge>
        </div>
        <div>
          <div className={styles.metaLabel}>Data scope</div>
          <div className={styles.metaValue}>{doc.data_scope}</div>
        </div>
        <div>
          <div className={styles.metaLabel}>Pages</div>
          <div className={styles.metaValue}>{doc.page_count}</div>
        </div>
        <div>
          <div className={styles.metaLabel}>Uploaded</div>
          <div className={styles.metaValue}>{new Date(doc.uploaded_at * 1000).toLocaleString()}</div>
        </div>
      </div>

      {doc.error && <p style={{ color: "var(--interlock)", fontSize: 12, marginBottom: "var(--space-4)" }}>{doc.error}</p>}

      {error && <p style={{ color: "var(--interlock)", fontSize: 12 }}>{error}</p>}
      {!error && (blobUrl ? <embed src={blobUrl} type={doc.content_type} className={styles.viewer} /> : <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Loading file…</p>)}
    </div>
  );
}
