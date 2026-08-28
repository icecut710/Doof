import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

export type ToastKind = "success" | "error" | "info";
type Toast = { id: number; kind: ToastKind; text: string };

const ToastCtx = createContext<(kind: ToastKind, text: string) => void>(() => {});

/** Returns push(kind, text) — toasts auto-dismiss after 4s (errors 6s). */
export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = nextId.current++;
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, kind === "error" ? 6000 : 4000);
  }, []);

  const value = useMemo(() => push, [push]);

  const tone: Record<ToastKind, string> = {
    success: "border-emerald-400/25 bg-emerald-950/60 text-emerald-200",
    error: "border-rose-400/25 bg-rose-950/60 text-rose-200",
    info: "border-violet-400/25 bg-violet-950/50 text-violet-200",
  };
  const icon: Record<ToastKind, string> = {
    success: "✓",
    error: "✕",
    info: "·",
  };

  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col items-end gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`doof-fade pointer-events-auto flex max-w-[320px] items-start gap-2 rounded-xl border px-3 py-2 text-[12px] leading-snug shadow-lg backdrop-blur-md ${tone[t.kind]}`}
          >
            <span className="mt-px shrink-0 font-semibold">{icon[t.kind]}</span>
            <span className="min-w-0 break-words">{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
