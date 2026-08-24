import type {
  AuditLogEntry,
  ChatResponse,
  DocumentRecord,
  GraphLineage,
  HealthReport,
  LoginResponse,
  MemoryEntry,
  ModelManifestEntry,
  QuarantineAlert,
  UploadResult,
  User,
} from "./types";

const TOKEN_KEY = "bastion_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "The backend is unreachable. Confirm it is running and reachable at this address.");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),

  me: () => request<{ user: User }>("/auth/me"),

  chat: (payload: { prompt: string; image_doc_id?: string; user_approved?: boolean; expected_step_index?: number }) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(payload) }),

  models: () => request<{ models: ModelManifestEntry[] }>("/models"),

  reloadManifest: () => request<{ status: string; count: number }>("/models/reload", { method: "POST" }),

  addModel: (payload: Record<string, unknown>) =>
    request<{ status: string; model: ModelManifestEntry }>("/admin/models/add", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listDocuments: () => request<{ documents: DocumentRecord[] }>("/documents"),

  uploadDocument: (file: File, dataScope?: string, allowedRoles?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (dataScope) form.append("data_scope", dataScope);
    if (allowedRoles) form.append("allowed_roles", allowedRoles);
    return request<UploadResult>("/documents/upload", { method: "POST", body: form });
  },

  // Fetched as an authenticated blob rather than a plain <iframe src> URL, since
  // the file endpoint requires a bearer token that only a real fetch() can send —
  // and a blob URL never puts the session token in browser history or server logs.
  async fetchDocumentBlob(docId: string): Promise<Blob> {
    const token = getToken();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`/v1/documents/${docId}/file`, { headers });
    if (!res.ok) throw new ApiError(res.status, `Could not load file for document ${docId}.`);
    return res.blob();
  },

  graphLineage: (equipmentId: string) => request<GraphLineage>(`/graph/lineage/${equipmentId}`),

  parsePid: (docId: string) => request<{ ocr_extraction: Record<string, unknown>; graph_lineage: GraphLineage | null }>(`/multimodal/parse-pid/${docId}`, { method: "POST" }),

  auditLogs: () => request<{ logs: AuditLogEntry[] }>("/admin/audit-logs"),

  verifyAuditChain: () => request<{ valid: boolean; checked_rows?: number; broken_at?: string; reason?: string }>("/admin/audit-logs/verify"),

  quarantineAlerts: () => request<{ alerts: QuarantineAlert[] }>("/admin/quarantine-alerts"),

  memory: () => request<{ memories: MemoryEntry[] }>("/mnemoshield/memory"),

  purgeMemory: (entryId: string) => request<{ status: string }>(`/mnemoshield/memory/${entryId}`, { method: "DELETE" }),

  consolidateMemory: (threshold = 2.5) =>
    request<{ initial_count: number; final_count: number; purged_count: number }>(`/mnemoshield/memory/consolidate?threshold=${threshold}`, { method: "POST" }),

  health: () => request<HealthReport>("/health"),
};
