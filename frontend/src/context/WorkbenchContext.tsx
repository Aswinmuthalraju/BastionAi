import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api } from "../api/client";
import type { ChatResponse } from "../api/types";

export interface ChatTurn {
  id: string;
  prompt: string;
  imageDocId?: string;
  imageName?: string;
  response?: ChatResponse;
  pending: boolean;
  error?: string;
}

export interface HistorySession {
  id: string;
  title: string;
  updatedAt: number;
  turns: ChatTurn[];
}

interface WorkbenchContextType {
  turns: ChatTurn[];
  input: string;
  pendingImage: { docId: string; filename: string } | null;
  uploadError: string | null;
  historySessions: HistorySession[];
  activeSessionId: string | null;
  isHistoryOpen: boolean;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  setPendingImage: React.Dispatch<React.SetStateAction<{ docId: string; filename: string } | null>>;
  setUploadError: React.Dispatch<React.SetStateAction<string | null>>;
  runTurn: (turnId: string, prompt: string, imageDocId?: string, userApproved?: boolean) => Promise<void>;
  clearTurns: () => void;
  removeTurn: (turnId: string) => void;
  addTurn: (turn: ChatTurn) => void;
  toggleHistory: () => void;
  loadSession: (sessionId: string) => void;
  startNewChat: () => void;
  deleteSession: (sessionId: string, e?: React.MouseEvent) => void;
}

const LOCAL_STORAGE_HISTORY_KEY = "bastion_workbench_history";

function loadSavedHistory(): HistorySession[] {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistorySession[];
    if (Array.isArray(parsed)) {
      return parsed.map((s) => ({
        ...s,
        turns: (s.turns || []).map((t) => ({ ...t, pending: false })),
      }));
    }
  } catch {
    // Ignore parse errors
  }
  return [];
}

const WorkbenchContext = createContext<WorkbenchContextType | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  // Page reload starts with an empty turns array (workbench cleared on reload as requested)
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<{ docId: string; filename: string } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [historySessions, setHistorySessions] = useState<HistorySession[]>(loadSavedHistory);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);

  // Sync history sessions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_HISTORY_KEY, JSON.stringify(historySessions));
    } catch {
      // Ignore storage errors
    }
  }, [historySessions]);

  // Sync active turns into current or new history session whenever turns update
  useEffect(() => {
    if (turns.length === 0) return;

    setHistorySessions((prev) => {
      const now = Date.now();
      const firstPrompt = turns[0].prompt;
      const title = firstPrompt.length > 40 ? `${firstPrompt.slice(0, 40)}…` : firstPrompt;

      if (activeSessionId) {
        const exists = prev.some((s) => s.id === activeSessionId);
        if (exists) {
          return prev.map((s) =>
            s.id === activeSessionId ? { ...s, title: s.title || title, updatedAt: now, turns } : s
          );
        }
      }

      // Create new session if none active
      const newId = `sess-${now}-${Math.random().toString(36).slice(2, 6)}`;
      setActiveSessionId(newId);
      return [{ id: newId, title, updatedAt: now, turns }, ...prev];
    });
  }, [turns, activeSessionId]);

  const toggleHistory = useCallback(() => {
    setIsHistoryOpen((prev) => !prev);
  }, []);

  const runTurn = useCallback(async (turnId: string, prompt: string, imageDocId?: string, userApproved = false) => {
    setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, pending: true, error: undefined } : t)));
    try {
      const response = await api.chat({ prompt, image_doc_id: imageDocId, user_approved: userApproved });
      setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, response, pending: false } : t)));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Request failed unexpectedly.";
      setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, pending: false, error: message } : t)));
    }
  }, []);

  const addTurn = useCallback((turn: ChatTurn) => {
    setTurns((prev) => [...prev, turn]);
  }, []);

  const removeTurn = useCallback((turnId: string) => {
    setTurns((prev) => prev.filter((t) => t.id !== turnId));
  }, []);

  const startNewChat = useCallback(() => {
    setTurns([]);
    setInput("");
    setPendingImage(null);
    setUploadError(null);
    setActiveSessionId(null);
  }, []);

  const clearTurns = useCallback(() => {
    startNewChat();
  }, [startNewChat]);

  const loadSession = useCallback(
    (sessionId: string) => {
      const target = historySessions.find((s) => s.id === sessionId);
      if (!target) return;
      setActiveSessionId(target.id);
      setTurns(target.turns);
      setInput("");
      setPendingImage(null);
      setUploadError(null);
    },
    [historySessions]
  );

  const deleteSession = useCallback((sessionId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setHistorySessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (activeSessionId === sessionId) {
      setTurns([]);
      setActiveSessionId(null);
    }
  }, [activeSessionId]);

  return (
    <WorkbenchContext.Provider
      value={{
        turns,
        input,
        pendingImage,
        uploadError,
        historySessions,
        activeSessionId,
        isHistoryOpen,
        setInput,
        setPendingImage,
        setUploadError,
        runTurn,
        clearTurns,
        removeTurn,
        addTurn,
        toggleHistory,
        loadSession,
        startNewChat,
        deleteSession,
      }}
    >
      {children}
    </WorkbenchContext.Provider>
  );
}

export function useWorkbench(): WorkbenchContextType {
  const ctx = useContext(WorkbenchContext);
  if (!ctx) {
    throw new Error("useWorkbench must be used within a WorkbenchProvider");
  }
  return ctx;
}
