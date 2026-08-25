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

interface WorkbenchContextType {
  turns: ChatTurn[];
  input: string;
  pendingImage: { docId: string; filename: string } | null;
  uploadError: string | null;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  setPendingImage: React.Dispatch<React.SetStateAction<{ docId: string; filename: string } | null>>;
  setUploadError: React.Dispatch<React.SetStateAction<string | null>>;
  runTurn: (turnId: string, prompt: string, imageDocId?: string, userApproved?: boolean) => Promise<void>;
  clearTurns: () => void;
  removeTurn: (turnId: string) => void;
  addTurn: (turn: ChatTurn) => void;
}

const SESSION_STORAGE_KEY = "bastion_workbench_turns";

function loadSavedTurns(): ChatTurn[] {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatTurn[];
    if (Array.isArray(parsed)) {
      return parsed.map((t) => ({
        ...t,
        pending: false,
      }));
    }
  } catch {
    // Ignore storage parse errors
  }
  return [];
}

const WorkbenchContext = createContext<WorkbenchContextType | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [turns, setTurns] = useState<ChatTurn[]>(loadSavedTurns);
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<{ docId: string; filename: string } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(turns));
    } catch {
      // Ignore storage errors
    }
  }, [turns]);

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

  const clearTurns = useCallback(() => {
    setTurns([]);
    try {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  }, []);

  return (
    <WorkbenchContext.Provider
      value={{
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
