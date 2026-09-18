"use client";

import { X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

type ToastTone = "info" | "done" | "error" | "attention";

export type ToastInput = {
  message: ReactNode;
  detail?: ReactNode;
  tone?: ToastTone;
  /** Undo and the like. The toast closes once the action resolves. */
  action?: { label: string; run: () => void | Promise<void> };
  /** ms before it goes by itself. Undo toasts stay longer by default. */
  duration?: number;
};

type ToastItem = ToastInput & { id: number };

type ToastApi = {
  toast: (input: ToastInput) => number;
  dismiss: (id: number) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast needs a ToastProvider above it");
  return value;
}

const marks: Record<ToastTone, string> = {
  info: "bg-muted",
  done: "bg-ready",
  attention: "bg-missing",
  error: "bg-build",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback((input: ToastInput) => {
    counter.current += 1;
    const id = counter.current;
    setItems((current) => [...current.slice(-3), { ...input, id }]);
    return id;
  }, []);

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        aria-relevant="additions"
        className="pointer-events-none fixed right-4 z-50 flex w-[min(420px,calc(100vw-2rem))] flex-col gap-2"
        style={{ bottom: "calc(var(--dock-h, 0px) + 1rem)" }}
      >
        {items.map((item) => (
          <ToastCard key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const [busy, setBusy] = useState(false);
  const [paused, setPaused] = useState(false);
  const duration = item.duration ?? (item.action ? 9000 : item.tone === "error" ? 10000 : 5000);

  useEffect(() => {
    if (paused || busy) return;
    const timer = window.setTimeout(() => onDismiss(item.id), duration);
    return () => window.clearTimeout(timer);
  }, [paused, busy, duration, item.id, onDismiss]);

  return (
    <div
      role={item.tone === "error" ? "alert" : "status"}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className="motion-toast pointer-events-auto flex items-start gap-3 rounded-[var(--radius-control)] border border-hairline bg-panel px-4 py-3 shadow-[0_12px_32px_rgb(0_0_0/0.4)]"
    >
      <span aria-hidden className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${marks[item.tone ?? "info"]}`} />
      <div className="min-w-0 flex-1 text-sm">
        <div className="font-medium break-words">{item.message}</div>
        {item.detail ? <div className="mt-0.5 break-words text-muted">{item.detail}</div> : null}
      </div>
      {item.action ? (
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await item.action?.run();
            } finally {
              onDismiss(item.id);
            }
          }}
          className="-my-1 h-8 shrink-0 rounded-[var(--radius-control)] px-2.5 text-sm font-semibold text-text underline decoration-hairline underline-offset-4 hover:decoration-text disabled:opacity-50"
        >
          {busy ? "Working" : item.action.label}
        </button>
      ) : null}
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        aria-label="Dismiss"
        className="-my-1 -mr-2 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] text-muted hover:text-text"
      >
        <X size={16} aria-hidden />
      </button>
    </div>
  );
}
