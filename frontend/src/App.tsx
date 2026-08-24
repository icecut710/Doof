import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getToken, storeToken, clearToken, type Profile } from "./auth";
import { cacheGet, cacheSet, cacheAge, cacheInvalidate, dedupe } from "./cache";
import Login from "./Login";
import { doofAudio } from "./audio";
import Boot from "./Boot";
import StatusTab from "./StatusTab";
import { friendlyError } from "./errors";

/* =========================================================
   TYPES
   ========================================================= */

type Page = "chat" | "memory" | "training" | "status" | "models" | "settings";

type Msg = {
  id: string;
  role: "user" | "doof";
  text: string;
  pending?: boolean;
  memoriesUsed?: MemoryItem[];
  feedback?: "good" | "bad" | null;
  correcting?: boolean;
  correction?: string;
};

type MemoryItem = {
  id: string;
  content: string;
  importance: "low" | "medium" | "high";
  category: string;
  created_by: string;
  created_at: string;
  usage_count: number;
  approved: boolean;
  tags?: string[];
  score?: number;
};

type MemoryStats = {
  total: number;
  approved: number;
  pending: number;
  high_importance: number;
};

type TrainingQueueItem = {
  id: string;
  type: string;
  priority: number;
  created_at: string;
  payload: Record<string, unknown>;
  assigned_worker: string | null;
};

type RunningJob = {
  id: string;
  step: number | null;
  epoch: number | null;
  total_epochs: number | null;
  loss: number | null;
  worker: string | null;
};

type TrainState = {
  running: boolean;
  step: number;
  loss: number | null;
  epoch: number;
  message: string;
  history: { step: number; loss: number }[];
  speed: number | null;
  eta_seconds: number | null;
  approved_examples: number;
  training_ready_examples: number;
  memory_count: number;
  brain_version: string;
  dataset_version: string | null;
  examples_count: number;
  total_feedback: number;
  workers_online: number;
  training_queue: TrainingQueueItem[];
  running_jobs: RunningJob[];
  online_nodes: NodeItem[];
};

type CheckpointItem = {
  name: string;
  path: string;
  size_mb: number;
  mtime: number;
  loaded: boolean;
  step: number | null;
  loss: number | null;
  status: "production" | "candidate" | "archived";
  version_label: string | null;
};

type NodeItem = {
  id: string;
  name: string;
  gpu: string;
  vram_gb: number;
  device: string;
  status: "online" | "offline";
  is_local?: boolean;
  training_active?: boolean;
  last_seen?: number;
};

type HardwareInfo = {
  device: string;
  cuda_available: boolean;
  cuda_devices: { name: string; total_memory_gb: number }[];
  mps_available: boolean;
  torch_version: string | null;
  platform: string;
  python: string;
  cpu_count: number | null;
  machine: string;
};

type Data = Record<string, unknown>;

function serverBase(): string {
  try {
    const stored = localStorage.getItem("doof_server");
    if (stored) return stored;
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined") {
    const port = window.location.port;
    // Desktop shell serves UI on 8766 / 3000 and API on 8765.
    if (port === "8766" || port === "3000") return "http://127.0.0.1:8765";
  }
  return "";
}

async function api<T = Data>(path: string, opts?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${serverBase()}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts?.headers ?? {}),
    },
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new Error(
      (json as { error?: string }).error ?? res.statusText ?? "Request failed",
    );
  return json as T;
}

/** Cached GET: serves instantly from memory, refreshes in background.
 *  Identical concurrent requests are coalesced into one network call. */
async function apiCached<T = Data>(path: string, ttlMs = 5000): Promise<T> {
  const cached = cacheGet<T>(path);
  const revalidate = () =>
    dedupe(path, () => api<T>(path))
      .then((fresh) => cacheSet(path, fresh))
      .catch(() => {});

  if (cached !== null) {
    const entryAge = Date.now() - (cacheAge(path) ?? 0);
    if (entryAge > ttlMs) void revalidate(); // background — never blocks
    return cached;
  }
  const data = await dedupe(path, () => api<T>(path));
  cacheSet(path, data);
  return data;
}

function uid() {
  return Math.random().toString(36).slice(2, 9);
}

/* =========================================================
   DESIGN SYSTEM
   ========================================================= */

// GlassPanel
function GlassPanel({
  children,
  className = "",
  glow = false,
}: {
  children: ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return (
    <div
      className={[
        "rounded-2xl border border-white/[0.055]",
        "bg-[#09090b]/90 backdrop-blur-sm",
        glow
          ? "shadow-[0_0_0_1px_rgba(139,92,246,0.08),0_8px_30px_rgba(0,0,0,0.22),0_0_40px_rgba(139,92,246,0.04)]"
          : "shadow-[0_8px_30px_rgba(0,0,0,0.18)]",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}

// GlassButton
function GlassButton({
  children,
  onClick,
  disabled,
  variant = "primary",
  size = "md",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger" | "success";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const variantCls =
    variant === "primary"
      ? "border-violet-400/20 bg-violet-600/80 text-white shadow-[0_4px_18px_rgba(124,58,237,0.16)] hover:bg-violet-500 hover:border-violet-300/25 hover:shadow-[0_4px_24px_rgba(124,58,237,0.28)]"
      : variant === "danger"
        ? "border-rose-500/20 bg-rose-500/[0.08] text-rose-300 hover:bg-rose-500/[0.14] hover:border-rose-400/25"
        : variant === "success"
          ? "border-emerald-400/20 bg-emerald-500/[0.08] text-emerald-300 hover:bg-emerald-500/[0.14]"
          : "border-white/[0.07] bg-white/[0.018] text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300";

  const sizeCls =
    size === "sm"
      ? "px-2.5 py-1 text-[12px]"
      : size === "lg"
        ? "px-5 py-2.5 text-[11px]"
        : "px-3.5 py-1.5 text-[10px]";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "rounded-xl border font-medium transition-all duration-200",
        "disabled:cursor-not-allowed disabled:opacity-30",
        variantCls,
        sizeCls,
        className,
      ].join(" ")}
    >
      {children}
    </button>
  );
}

// StatusBadge
function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "online" | "violet" | "danger" | "warning";
}) {
  const toneCls =
    tone === "online"
      ? "border-emerald-400/15 bg-emerald-400/[0.045] text-emerald-400/90"
      : tone === "violet"
        ? "border-violet-400/20 bg-violet-500/[0.065] text-violet-300/90"
        : tone === "danger"
          ? "border-rose-400/15 bg-rose-400/[0.045] text-rose-400/90"
          : tone === "warning"
            ? "border-amber-400/15 bg-amber-400/[0.045] text-amber-400/90"
            : "border-white/[0.065] bg-white/[0.018] text-zinc-500";
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border",
        "px-2 py-0.5 text-[12px] uppercase tracking-[0.13em]",
        toneCls,
      ].join(" ")}
    >
      {children}
    </span>
  );
}

// MetricCard
function MetricCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={[
        "rounded-xl border px-3 py-2.5",
        "shadow-[0_4px_18px_rgba(0,0,0,0.12)]",
        accent
          ? "border-violet-400/12 bg-violet-500/[0.04]"
          : "border-white/[0.045] bg-white/[0.012]",
      ].join(" ")}
    >
      <div className="text-[12px] font-medium uppercase tracking-[0.14em] text-zinc-700">
        {label}
      </div>
      <div
        className={[
          "mt-1 truncate text-[13px] font-semibold tracking-tight",
          accent ? "text-violet-300" : "text-zinc-200",
        ].join(" ")}
      >
        {value}
      </div>
      {sub && (
        <div className="mt-0.5 text-[12px] text-zinc-700">{sub}</div>
      )}
    </div>
  );
}


// StatusDot
function StatusDot({ on }: { on: boolean }) {
  return (
    <span
      className={[
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
        on
          ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]"
          : "bg-zinc-700",
      ].join(" ")}
    />
  );
}

/* =========================================================
   STAR FIELD
   ========================================================= */

function StarField() {
  const stars = useMemo(
    () =>
      Array.from({ length: 26 }, (_, i) => ({
        left: `${(i * 23.37 + 7) % 100}%`,
        top: `${(i * 41.13 + 11) % 100}%`,
        size: i % 9 === 0 ? 1.5 : 1,
        opacity: 0.05 + ((i * 17) % 18) / 100,
        // Only a few stars gently pulse — static dots are free.
        twinkle: i < 6,
        delay: `${(i % 6) * 0.8}s`,
      })),
    [],
  );
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {stars.map((s, i) => (
        <span
          key={i}
          className={s.twinkle ? "absolute rounded-full bg-white doof-pulse" : "absolute rounded-full bg-white"}
          style={{
            left: s.left,
            top: s.top,
            width: s.size,
            height: s.size,
            opacity: s.opacity,
            animationDelay: s.twinkle ? s.delay : undefined,
          }}
        />
      ))}
    </div>
  );
}

/* =========================================================
   NADDAF ATMOSPHERE
   ========================================================= */

const NADDAF_LOCAL = "./mrnaddaf.png";
const NADDAF_REMOTE =
  "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/mrnaddaf.png";

function NaddafAtmosphere() {
  // Bundled asset renders immediately — no network wait, no flash, no shift.
  // Once per launch, a single background attempt may adopt the canonical
  // Supabase copy; on any failure we silently keep the bundled one.
  const [src, setSrc] = useState(NADDAF_LOCAL);
  useEffect(() => {
    let alive = true;
    fetch(NADDAF_REMOTE, { mode: "cors", cache: "force-cache" })
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (alive && blob) setSrc(URL.createObjectURL(blob));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <StarField />

      {/* Naddaf image — centered, cinematic */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className="absolute left-1/2 top-1/2 h-[96%] w-[96%] -translate-x-1/2 -translate-y-1/2"
          style={{
            WebkitMaskImage:
              "radial-gradient(ellipse 76% 74% at 50% 50%, black 5%, rgba(0,0,0,.97) 32%, rgba(0,0,0,.78) 60%, rgba(0,0,0,.28) 82%, transparent 100%)",
            maskImage:
              "radial-gradient(ellipse 76% 74% at 50% 50%, black 5%, rgba(0,0,0,.97) 32%, rgba(0,0,0,.78) 60%, rgba(0,0,0,.28) 82%, transparent 100%)",
          }}
        >
          <img
            src={src}
            alt=""
            draggable={false}
            className="h-full w-full scale-105 object-contain object-center blur-[4px] opacity-[0.34] saturate-[0.9]"
          />
        </div>
      </div>

      {/* Dark overlay — readable text, recognizable scene behind it */}
      <div className="absolute inset-0 bg-black/[0.72]" />

      {/* Violet center glow */}
      <div className="absolute left-1/2 top-1/2 h-[480px] w-[480px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-700/[0.065] blur-[140px] doof-beat-glow" />
      {/* Subtle white aura around figure */}
      <div className="absolute left-1/2 top-1/2 h-[320px] w-[260px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/[0.018] blur-[80px] doof-beat-aura" />

      {/* Radial vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(3,3,4,.06)_40%,rgba(3,3,4,.55)_100%)]" />
      {/* Cinematic edges */}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/80 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-black/90 to-transparent" />
      <div className="absolute inset-y-0 left-0 w-36 bg-gradient-to-r from-[#030304]/92 to-transparent" />
      <div className="absolute inset-y-0 right-0 w-36 bg-gradient-to-l from-[#030304]/65 to-transparent" />
    </div>
  );
}

/* =========================================================
   SIDEBAR
   ========================================================= */

const NAV_ITEMS: { id: Page; label: string; icon: string; section: string }[] = [
  { id: "chat", label: "Chat", icon: "*", section: "CHAT" },
  { id: "memory", label: "Memory", icon: "+", section: "CHAT" },
  { id: "training", label: "Training", icon: "T", section: "CHAT" },
  { id: "status", label: "Status", icon: "S", section: "HOUSE" },
  { id: "models", label: "Brain", icon: "B", section: "HOUSE" },
  { id: "settings", label: "Settings", icon: "=", section: "HOUSE" },
];

function Sidebar({
  page,
  setPage,
  online,
  hw,
  trainRunning,
}: {
  page: Page;
  setPage: (p: Page) => void;
  online: boolean;
  hw: HardwareInfo | null;
  trainRunning: boolean;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const sections = ["CHAT", "HOUSE"];
  const gpuName =
    hw?.cuda_available && hw.cuda_devices[0]
      ? hw.cuda_devices[0].name
      : hw?.mps_available
        ? "Apple MPS"
        : "CPU";

  return (
    <aside
      className={[
        "flex shrink-0 flex-col border-r border-white/[0.045]",
        "bg-[#030304]/96 backdrop-blur-xl transition-all duration-200",
        collapsed ? "w-[52px]" : "w-[180px]",
      ].join(" ")}
    >
      {/* Logo */}
      <div className="flex h-[46px] shrink-0 items-center gap-2 border-b border-white/[0.045] px-3">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] border border-violet-400/20 bg-violet-500/[0.065] text-[12px] font-bold text-violet-300 shadow-[0_0_14px_rgba(124,58,237,0.1)] doof-logo-beat">
          D
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold tracking-tight text-zinc-100">DOOF</div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-700">
              v0.2 · local
            </div>
          </div>
        )}
        {!collapsed && (
          <button
            type="button"
            title="Collapse sidebar"
            onClick={() => setCollapsed(true)}
            className="text-[12px] text-zinc-800 transition hover:text-violet-300"
          >
            {'<'}
          </button>
        )}
      </div>
      {collapsed && (
        <button
          type="button"
          title="Expand sidebar"
          onClick={() => setCollapsed(false)}
          className="mx-auto mt-2 text-[10px] text-zinc-700 transition hover:text-violet-300"
        >
          {'>'}
        </button>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-1.5 py-2">
        {sections.map((section) => {
          const items = NAV_ITEMS.filter((n) => n.section === section);
          if (!items.length) return null;
          return (
            <div key={section} className="mb-3">
              <div className="mb-1 px-2 text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-800">
                {section}
              </div>
              {items.map((item) => {
                const active = page === item.id;
                const isTraining = item.id === "training" && trainRunning;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setPage(item.id)}
                    className={[
                      "mb-0.5 flex w-full items-center gap-2",
                      "rounded-xl px-2 py-1.5 text-left",
                      "text-[13px] transition-all duration-200",
                      active
                        ? "bg-violet-500/[0.11] text-violet-200 shadow-[inset_0_0_0_1px_rgba(139,92,246,0.18),0_0_18px_rgba(139,92,246,0.12)] doof-nav-active-beat"
                        : "text-zinc-400 hover:bg-white/[0.025] hover:text-zinc-100",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "w-3.5 shrink-0 text-center text-[12px]",
                        active ? "text-violet-400" : "text-zinc-500",
                      ].join(" ")}
                    >
                      {item.icon}
                    </span>
                    {!collapsed && <span className="flex-1">{item.label}</span>}
                    {isTraining && !collapsed && (
                      <span className="h-1.5 w-1.5 rounded-full bg-violet-400 shadow-[0_0_6px_rgba(139,92,246,0.8)]" />
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="shrink-0 border-t border-white/[0.045] px-2.5 py-2">
        <div className="flex items-center gap-1.5">
          <StatusDot on={online} />
          <span className="text-[12px] uppercase tracking-[0.13em] text-zinc-400">
            {online ? "Shawarmas: Fresh" : "Lost in the desert"}
          </span>
        </div>
        <div className="mt-0.5 truncate text-[12px] text-zinc-500" title={gpuName}>
          {online ? "All core services responding" : "The brain is unreachable"}
        </div>
      </div>
    </aside>
  );
}

/* =========================================================
   CHAT TAB
   ========================================================= */

function ChatTab({
  msgs,
  setMsgs,
  input,
  setInput,
  busy,
  setBusy,
  online,
  sett,
  inputRef,
  bottomRef,
}: {
  msgs: Msg[];
  setMsgs: React.Dispatch<React.SetStateAction<Msg[]>>;
  input: string;
  setInput: (v: string) => void;
  busy: boolean;
  setBusy: (v: boolean) => void;
  online: boolean;
  sett: { temperature: number; max_new_tokens: number; top_k: number };
  inputRef: React.RefObject<HTMLInputElement | null>;
  bottomRef: React.RefObject<HTMLDivElement | null>;
}) {
  const SUGGESTIONS = [
    "What have you learned?",
    "Tell me about yourself",
    "What is my training status?",
    "What do you remember?",
  ];

  const send = async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text || busy || !online) return;
    if (!override) setInput("");

    const msgId = uid();
    setMsgs((cur) => [
      ...cur,
      { id: uid(), role: "user", text },
      { id: msgId, role: "doof", text: "···", pending: true },
    ]);
    setBusy(true);

    try {
      const data = await api<{
        text?: string;
        memories_used?: MemoryItem[];
      }>("/api/generate", {
        method: "POST",
        body: JSON.stringify({
          prompt: text,
          temperature: sett.temperature,
          max_new_tokens: sett.max_new_tokens,
          top_k: sett.top_k,
        }),
      });

      const output = data.text?.trim() || "(empty response)";
      setMsgs((cur) =>
        cur.map((m) =>
          m.id === msgId
            ? {
                ...m,
                text: output,
                pending: false,
                memoriesUsed: data.memories_used ?? [],
                feedback: null,
              }
            : m,
        ),
      );
    } catch (err) {
      const friendly = friendlyError(err);
      setMsgs((cur) =>
        cur.map((m) =>
          m.id === msgId
            ? {
                ...m,
                text: `${friendly.title}\n${friendly.body}`,
                pending: false,
              }
            : m,
        ),
      );
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  const sendFeedback = async (msg: Msg, rating: "good" | "bad") => {
    setMsgs((cur) =>
      cur.map((m) =>
        m.id === msg.id
          ? { ...m, feedback: rating, correcting: rating === "bad" }
          : m,
      ),
    );
    // If good, submit immediately
    if (rating === "good") {
      try {
        const prevUser = msgs[msgs.findIndex((m) => m.id === msg.id) - 1];
        await api("/api/feedback", {
          method: "POST",
          body: JSON.stringify({
            prompt: prevUser?.text ?? "",
            response: msg.text,
            rating: "good",
            memories_used: msg.memoriesUsed ?? [],
          }),
        });
      } catch {
        // silent
      }
    }
  };

  const submitCorrection = async (msg: Msg) => {
    const correction = msg.correction?.trim() ?? "";
    if (!correction) return;
    try {
      const prevUser = msgs[msgs.findIndex((m) => m.id === msg.id) - 1];
      await api("/api/feedback", {
        method: "POST",
        body: JSON.stringify({
          prompt: prevUser?.text ?? "",
          response: msg.text,
          rating: "bad",
          correction,
          memories_used: msg.memoriesUsed ?? [],
        }),
      });
    } catch {
      // silent
    }
    setMsgs((cur) =>
      cur.map((m) =>
        m.id === msg.id ? { ...m, correcting: false, correction: "" } : m,
      ),
    );
  };

  return (
    <>
      <div className="relative flex-1 overflow-hidden">
        <div className="absolute inset-0 overflow-y-auto px-4 py-3">
          {msgs.length === 0 ? (
            <div className="flex min-h-full items-center justify-center">
              <div className="relative z-10 -mt-8 w-full max-w-[380px] text-center">
                <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-[12px] border border-violet-400/15 bg-violet-500/[0.055] text-[13px] font-semibold text-violet-300/85 shadow-[0_0_24px_rgba(124,58,237,0.1)]">
                  D
                </div>
                <h1 className="mt-2.5 text-[17px] font-semibold tracking-[-0.03em] text-zinc-100">
                  DOOF
                </h1>
                <p className="mt-0.5 text-[12px] text-zinc-500">
                  your little evolving brain · ready to learn
                </p>
                <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                  <StatusBadge tone={online ? "online" : "neutral"}>
                    <StatusDot on={online} />
                    {online ? "Shawarmas: Fresh" : "Lost in the desert"}
                  </StatusBadge>
                </div>
                <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={!online || busy}
                      onClick={() => void send(s)}
                      className="rounded-full border border-white/[0.055] bg-black/50 px-2.5 py-1.5 text-[12px] text-zinc-600 transition-all hover:border-violet-500/25 hover:bg-violet-500/[0.055] hover:text-zinc-300 disabled:opacity-30"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-[620px] space-y-2 pb-3">
              {msgs.map((msg) => (
                <div
                  key={msg.id}
                  className={["flex flex-col", msg.role === "user" ? "items-end" : "items-start"].join(" ")}
                >
                  <div
                    className={[
                      "max-w-[82%] rounded-2xl px-3 py-2",
                      "text-[13px] leading-relaxed",
                      msg.role === "user"
                        ? "border border-violet-400/10 bg-violet-600/20 text-zinc-100"
                        : "border border-white/[0.05] bg-[#09090a]/95 text-zinc-100",
                      msg.pending ? "opacity-50" : "",
                    ].join(" ")}
                  >
                    {msg.pending ? (
                      <span className="doof-pulse inline-block">···</span>
                    ) : (
                      msg.text
                    )}
                  </div>

                  {/* Memory indicator */}
                  {msg.role === "doof" &&
                    !msg.pending &&
                    msg.memoriesUsed &&
                    msg.memoriesUsed.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {msg.memoriesUsed.slice(0, 3).map((m) => (
                          <span
                            key={m.id}
                            className="rounded-full border border-violet-400/10 bg-violet-500/[0.04] px-1.5 py-0.5 text-[11px] text-violet-400/60"
                            title={m.content}
                          >
                            ✓ {m.content.slice(0, 28)}…
                          </span>
                        ))}
                      </div>
                    )}

                  {/* Feedback buttons */}
                  {msg.role === "doof" && !msg.pending && msg.feedback === null && (
                    <div className="mt-1 flex gap-1">
                      <button
                        type="button"
                        onClick={() => void sendFeedback(msg, "good")}
                        className="rounded-lg border border-white/[0.04] bg-white/[0.012] px-2 py-0.5 text-[12px] text-zinc-400 transition-all hover:border-emerald-400/20 hover:bg-emerald-400/[0.04] hover:text-emerald-400"
                      >
                        👍 Good
                      </button>
                      <button
                        type="button"
                        onClick={() => void sendFeedback(msg, "bad")}
                        className="rounded-lg border border-white/[0.04] bg-white/[0.012] px-2 py-0.5 text-[12px] text-zinc-400 transition-all hover:border-rose-400/20 hover:bg-rose-400/[0.04] hover:text-rose-400"
                      >
                        👎 Teach
                      </button>
                    </div>
                  )}

                  {/* Feedback state */}
                  {msg.role === "doof" && !msg.pending && msg.feedback === "good" && (
                    <div className="mt-1 text-[11px] text-emerald-400/60">
                      ✓ Saved to training data
                    </div>
                  )}

                  {/* Correction flow */}
                  {msg.role === "doof" && msg.correcting && (
                    <div className="mt-2 w-full max-w-[82%]">
                      <GlassPanel className="p-2.5">
                        <div className="mb-1.5 text-[12px] uppercase tracking-[0.12em] text-zinc-700">
                          What should DOOF have said?
                        </div>
                        <textarea
                          value={msg.correction ?? ""}
                          onChange={(e) =>
                            setMsgs((cur) =>
                              cur.map((m) =>
                                m.id === msg.id
                                  ? { ...m, correction: e.target.value }
                                  : m,
                              ),
                            )
                          }
                          rows={3}
                          placeholder="The correct answer is…"
                          className="w-full resize-none rounded-xl border border-white/[0.05] bg-black/40 p-2 text-[10px] text-zinc-300 outline-none placeholder:text-zinc-800 focus:border-violet-500/20"
                        />
                        <div className="mt-2 flex gap-1.5">
                          <GlassButton size="sm" onClick={() => void submitCorrection(msg)}>
                            Submit correction
                          </GlassButton>
                          <GlassButton
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setMsgs((cur) =>
                                cur.map((m) =>
                                  m.id === msg.id
                                    ? { ...m, correcting: false }
                                    : m,
                                ),
                              )
                            }
                          >
                            Cancel
                          </GlassButton>
                        </div>
                      </GlassPanel>
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="shrink-0 border-t border-white/[0.045] bg-[#000000]/95 px-4 py-2.5 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[620px] gap-1.5">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder={
              busy
                ? "DOOF is thinking…"
                : online
                  ? "Message DOOF…"
                  : "Couldn't reach the DOOF brain…"
            }
            disabled={!online || busy}
            className="min-w-0 flex-1 rounded-2xl border border-white/[0.06] bg-[#080809] px-3 py-2 text-[11px] text-zinc-200 outline-none shadow-[0_5px_24px_rgba(0,0,0,0.18)] placeholder:text-zinc-800 transition focus:border-violet-500/25 focus:shadow-[0_0_0_3px_rgba(139,92,246,0.04)] disabled:opacity-40"
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={!online || busy || !input.trim()}
            className="rounded-2xl border border-violet-400/20 bg-violet-600/80 px-3.5 py-2 text-[12px] font-medium text-white shadow-[0_5px_20px_rgba(124,58,237,0.12)] transition-all hover:bg-violet-500 disabled:opacity-25"
          >
            {busy ? "···" : "Send"}
          </button>
        </div>
        <div className="mt-1 text-center text-[11px] uppercase tracking-[0.15em] text-zinc-600">
          DOOF · local inference
        </div>
      </div>
    </>
  );
}

/* =========================================================
   MEMORY TAB
   ========================================================= */

function MemoryTab({ online }: { online: boolean }) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [stats, setStats] = useState<MemoryStats>({ total: 0, approved: 0, pending: 0, high_importance: 0 });
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newContent, setNewContent] = useState("");
  const [newImportance, setNewImportance] = useState<"low" | "medium" | "high">("medium");
  const [newCategory, setNewCategory] = useState("general");

  const load = useCallback(async () => {
    if (!online) return;
    setLoading(true);
    try {
      const data = await apiCached<{ memories: MemoryItem[]; stats: MemoryStats }>("/api/memory", 10000);
      setMemories(data.memories ?? []);
      setStats(data.stats ?? { total: 0, approved: 0, pending: 0, high_importance: 0 });
    } finally {
      setLoading(false);
    }
  }, [online]);

  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return q
      ? memories.filter((m) => m.content.toLowerCase().includes(q) || m.category.toLowerCase().includes(q))
      : memories;
  }, [memories, query]);

  const addMemory = async () => {
    if (!newContent.trim()) return;
    await api("/api/memory", {
      method: "POST",
      body: JSON.stringify({
        content: newContent.trim(),
        importance: newImportance,
        category: newCategory || "general",
      }),
    });
    setNewContent("");
    setShowAdd(false);
    cacheInvalidate("/api/memory");
    void load();
  };

  const deleteMemory = async (id: string) => {
    await api(`/api/memory/${id}`, { method: "DELETE" });
    cacheInvalidate("/api/memory");
    setMemories((m) => m.filter((x) => x.id !== id));
    setStats((s) => ({ ...s, total: s.total - 1, approved: s.approved - 1 }));
  };

  const importanceBadge = (imp: string) => {
    if (imp === "high") return <StatusBadge tone="violet">High</StatusBadge>;
    if (imp === "medium") return <StatusBadge tone="warning">Medium</StatusBadge>;
    return <StatusBadge tone="neutral">Low</StatusBadge>;
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-[12px] uppercase tracking-[0.18em] text-zinc-500">
            EVERYTHING DOOF REMEMBERS · FOREVER
          </div>
          <div className="mt-1 text-[13px] font-semibold text-zinc-100">MEMORY</div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-1.5">
        <MetricCard label="Total" value={stats.total} />
        <MetricCard label="Approved" value={stats.approved} accent />
        <MetricCard label="Pending" value={stats.pending} />
        <MetricCard label="High Priority" value={stats.high_importance} />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search memories…"
          className="flex-1 rounded-xl border border-white/[0.055] bg-[#080809] px-3 py-1.5 text-[10px] text-zinc-200 outline-none placeholder:text-zinc-600 focus:border-violet-500/20"
        />
        <GlassButton onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? "Cancel" : "+ Teach DOOF"}
        </GlassButton>
        <GlassButton variant="ghost" onClick={() => void load()}>
          ↻
        </GlassButton>
      </div>

      {/* Add form */}
      {showAdd && (
        <GlassPanel className="p-3" glow>
          <div className="mb-2 text-[12px] uppercase tracking-[0.15em] text-zinc-700">
            New Memory
          </div>
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            rows={2}
            placeholder="Enter memory content…"
            className="w-full resize-none rounded-xl border border-white/[0.05] bg-black/40 p-2 text-[10px] text-zinc-300 outline-none placeholder:text-zinc-800 focus:border-violet-500/20"
          />
          <div className="mt-2 flex items-center gap-2">
            <select
              value={newImportance}
              onChange={(e) => setNewImportance(e.target.value as "low" | "medium" | "high")}
              className="rounded-lg border border-white/[0.05] bg-black/50 px-2 py-1 text-[12px] text-zinc-400 outline-none"
            >
              <option value="low">Low importance</option>
              <option value="medium">Medium importance</option>
              <option value="high">High importance</option>
            </select>
            <input
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              placeholder="Category"
              className="flex-1 rounded-lg border border-white/[0.05] bg-black/50 px-2 py-1 text-[12px] text-zinc-400 outline-none placeholder:text-zinc-800 focus:border-violet-500/20"
            />
            <GlassButton size="sm" onClick={() => void addMemory()}>
              Save
            </GlassButton>
          </div>
        </GlassPanel>
      )}

      {/* Memory cards */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && memories.length === 0 && (
          <div className="py-12 text-center text-[10px] text-zinc-800">Loading…</div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="py-12 text-center text-[10px] text-zinc-800">
            {memories.length === 0 ? "No memories yet. Add the first one." : "No results."}
          </div>
        )}
        <div className="space-y-1.5">
          {filtered.map((mem) => (
            <div
              key={mem.id}
              className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.04] bg-white/[0.01] px-3 py-2.5 transition-all hover:border-white/[0.07] hover:bg-white/[0.015]"
            >
              <div className="min-w-0 flex-1">
                <div className="text-[10px] leading-snug text-zinc-300">{mem.content}</div>
                <div className="mt-1 flex items-center gap-2 text-[12px] text-zinc-700">
                  <span>{mem.category}</span>
                  <span>·</span>
                  <span>Used {mem.usage_count}×</span>
                  <span>·</span>
                  <span>by {mem.created_by}</span>
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                {importanceBadge(mem.importance)}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    title="Edit memory"
                    onClick={() => {
                      const next = window.prompt("Edit memory", mem.content);
                      if (!next || next.trim() === mem.content) return;
                      void (async () => {
                        try {
                          await api(`/api/memory/${mem.id}`, { method: "DELETE" });
                          await api("/api/memory", {
                            method: "POST",
                            body: JSON.stringify({
                              content: next.trim(),
                              importance: mem.importance,
                              category: mem.category,
                              created_by: mem.created_by,
                            }),
                          });
                          void load();
                        } catch { /* ignore */ }
                      })();
                    }}
                    className="text-[12px] text-zinc-800 transition hover:text-violet-300"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    title="Promote to training dataset"
                    onClick={() =>
                      void api("/api/approved_examples", {
                        method: "POST",
                        body: JSON.stringify({
                          prompt: "What do you know about this?",
                          response: mem.content,
                          source: "memory",
                          approved: true,
                        }),
                      })
                        .then(() => cacheInvalidate("/api/approved_examples"))
                        .then(() => void load())
                        .catch(() => {})
                    }
                    className="text-[12px] text-zinc-800 transition hover:text-emerald-400"
                  >
                    Promote to training
                  </button>
                  <button
                    type="button"
                    onClick={() => void deleteMemory(mem.id)}
                    className="text-[12px] text-zinc-800 transition hover:text-rose-400"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   TRAINING TAB
   ========================================================= */

function TrainingTab({ online }: { online: boolean }) {
  const [train, setTrain] = useState<TrainState>({
    running: false,
    step: 0,
    loss: null,
    epoch: 0,
    message: "idle",
    history: [],
    speed: null,
    eta_seconds: null,
    approved_examples: 0,
    training_ready_examples: 0,
    memory_count: 0,
    brain_version: "1.0.0",
    dataset_version: null,
    examples_count: 0,
    total_feedback: 0,
    workers_online: 0,
    training_queue: [],
    running_jobs: [],
    online_nodes: [],
  });

  const refresh = useCallback(async () => {
    if (!online) return;
    try {
      const data = await apiCached<TrainState>("/api/training", 1200);
      setTrain(data);
    } catch { /* ignore */ }
  }, [online]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    if (!online) return;
    const t = setInterval(() => void refresh(), 1200);
    return () => clearInterval(t);
  }, [online, refresh]);

  const [showLogs, setShowLogs] = useState(false);
  const [jobs, setJobs] = useState<{ id: string; status: string; created_at: string; worker: string | null }[]>([]);

  const loadJobs = useCallback(async () => {
    if (!online) return;
    try {
      const data = await api<typeof jobs>("/api/training/jobs");
      setJobs(Array.isArray(data) ? data : []);
    } catch { /* ignore */ }
  }, [online]);

  useEffect(() => {
    if (showLogs) void loadJobs();
  }, [showLogs, loadJobs]);

  const startTrain = async () => {
    await api("/api/training/start", { method: "POST", body: JSON.stringify({ epochs: 3 }) });
    void refresh();
  };

  const stopTrain = async () => {
    await api("/api/training/stop", { method: "POST", body: JSON.stringify({}) });
  };

  const buildDataset = async () => {
    await api("/api/training/build_dataset", { method: "POST", body: JSON.stringify({}) });
    void refresh();
  };

  const history = train.history ?? [];
  const lossValues = history.map((h) => Number(h.loss) || 0);
  const minLoss = lossValues.length ? Math.min(...lossValues) : 0;
  const maxLoss = lossValues.length ? Math.max(...lossValues) : 1;

  const etaStr = train.eta_seconds
    ? train.eta_seconds > 60
      ? `${Math.floor(train.eta_seconds / 60)}m ${train.eta_seconds % 60}s`
      : `${train.eta_seconds}s`
    : null;

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="text-[12px] uppercase tracking-[0.18em] text-zinc-500">
            MEMORY → FEEDBACK → TRAINING DATA → NEW BRAIN
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-[13px] font-semibold text-zinc-100">
              BRAIN v{train.brain_version}
            </span>
            <StatusBadge tone={train.running ? "violet" : "neutral"}>
              {train.running ? "● DOOF IS TRAINING" : "READY TO LEARN"}
            </StatusBadge>
          </div>
        </div>
        <div className="text-right">
          {train.dataset_version && (
            <div className="text-[12px] text-zinc-700">Dataset: {train.dataset_version}</div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="mb-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        <MetricCard
          label="Approved Examples"
          value={train.approved_examples}
          accent
        />
        <MetricCard label="Training Ready" value={train.training_ready_examples} />
        <MetricCard label="Memory Count" value={train.memory_count} />
        <MetricCard
          label="Current Step"
          value={train.step || "—"}
          sub={train.epoch ? `Epoch ${train.epoch}` : undefined}
        />
      </div>

      {/* Compute pool stats */}
      <div className="mb-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        <MetricCard label="Workers Online" value={train.workers_online} />
        <MetricCard
          label="Queue Depth"
          value={train.training_queue?.length ?? 0}
        />
        <MetricCard
          label="Total Feedback"
          value={train.total_feedback}
        />
        <MetricCard
          label="Examples Count"
          value={train.examples_count}
        />
      </div>

      {/* Live stats (during training) */}
      {train.running && (
        <GlassPanel className="mb-3 p-3" glow>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-center">
                <div className="text-[12px] uppercase tracking-[0.12em] text-zinc-700">Loss</div>
                <div className="text-[16px] font-semibold tabular-nums text-violet-300">
                  {train.loss != null ? Number(train.loss).toFixed(4) : "—"}
                </div>
              </div>
              {train.speed != null && (
                <div className="text-center">
                  <div className="text-[12px] uppercase tracking-[0.12em] text-zinc-700">Speed</div>
                  <div className="text-[16px] font-semibold tabular-nums text-zinc-200">
                    {train.speed.toFixed(1)}
                    <span className="text-[12px] text-zinc-600"> it/s</span>
                  </div>
                </div>
              )}
              {etaStr && (
                <div className="text-center">
                  <div className="text-[12px] uppercase tracking-[0.12em] text-zinc-700">ETA</div>
                  <div className="text-[16px] font-semibold tabular-nums text-zinc-200">
                    {etaStr}
                  </div>
                </div>
              )}
            </div>
            <div className="text-[12px] text-zinc-600">{train.message}</div>
          </div>
        </GlassPanel>
      )}

      {/* Training queue */}
      {train.training_queue && train.training_queue.length > 0 && (
        <GlassPanel className="mb-3 p-3">
          <div className="mb-1.5 text-[12px] uppercase tracking-[0.12em] text-zinc-700">
            Training Queue ({train.training_queue.length})
          </div>
          <div className="space-y-1">
            {train.training_queue.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-black/30 px-2.5 py-1.5"
              >
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="text-violet-400/60">↯</span>
                  <span className="text-zinc-300">{job.type}</span>
                  <StatusBadge tone="warning">Queued</StatusBadge>
                </div>
                <div className="text-[11px] text-zinc-600">
                  Priority {job.priority} · {job.assigned_worker ?? "Unassigned"}
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}

      {/* Running jobs */}
      {train.running_jobs && train.running_jobs.length > 0 && (
        <GlassPanel className="mb-3 p-3">
          <div className="mb-1.5 text-[12px] uppercase tracking-[0.12em] text-zinc-700">
            Running Jobs ({train.running_jobs.length})
          </div>
          <div className="space-y-1">
            {train.running_jobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-black/30 px-2.5 py-1.5"
              >
                <div className="text-[12px] text-zinc-300">Job {job.id.slice(0, 8)}…</div>
                <div className="flex items-center gap-3 text-[12px] text-zinc-600">
                  {job.epoch != null && <span>Epoch {job.epoch}</span>}
                  {job.total_epochs != null && <span>/ {job.total_epochs}</span>}
                  {job.step != null && <span>Step {job.step}</span>}
                  {job.loss != null && <span className="text-violet-300">Loss {Number(job.loss).toFixed(4)}</span>}
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}

      {/* Controls */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        <GlassButton onClick={() => void startTrain()} disabled={train.running || !online}>
          Start Training
        </GlassButton>
        <GlassButton
          variant="ghost"
          onClick={() => void stopTrain()}
          disabled={!train.running}
        >
          Stop
        </GlassButton>
        <GlassButton
          variant="ghost"
          onClick={() => void buildDataset()}
          disabled={train.running || !online}
        >
          Build Dataset
        </GlassButton>
        <GlassButton
          variant="ghost"
          onClick={() => {
            const text = window.prompt("Knowledge to teach DOOF (permanent):");
            if (!text?.trim()) return;
            void api("/api/knowledge", {
              method: "POST",
              body: JSON.stringify({ text: text.trim(), source: "upload" }),
            }).then(() => void refresh()).catch(() => {});
          }}
          disabled={!online}
        >
          Upload Knowledge
        </GlassButton>
        <GlassButton
          variant="ghost"
          onClick={() => setShowLogs(!showLogs)}
          disabled={!online}
        >
          {showLogs ? "Hide Logs" : "View Logs"}
        </GlassButton>
      </div>

      {/* Job logs */}
      {showLogs && (
        <GlassPanel className="mb-3 p-3">
          <div className="mb-1.5 text-[12px] uppercase tracking-[0.15em] text-zinc-700">
            Training Job Log
          </div>
          <div className="max-h-[140px] space-y-1 overflow-y-auto font-mono text-[12px] text-zinc-600">
            {(jobs.length === 0 && <div>No training jobs yet.</div>) ||
              jobs.map((j) => (
                <div key={j.id} className="truncate">
                  <span className={j.status === "done" ? "text-emerald-500/70" : "text-violet-400/70"}>
                    [{j.status}]
                  </span>{" "}
                  {j.created_at} · worker {j.worker ?? "—"}
                </div>
              ))}
          </div>
        </GlassPanel>
      )}

      {/* Loss curve */}
      <GlassPanel className="p-3.5">
        <div className="mb-2 text-[12px] uppercase tracking-[0.15em] text-zinc-700">
          Loss Curve
        </div>
        {history.length === 0 ? (
          <div className="py-10 text-center text-[10px] text-zinc-800">
            No training history yet.
          </div>
        ) : (
          <svg viewBox="0 0 400 100" className="h-24 w-full">
            <defs>
              <linearGradient id="lossGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(139,92,246)" stopOpacity="0.3" />
                <stop offset="100%" stopColor="rgb(139,92,246)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <polyline
              fill="none"
              stroke="rgb(139 92 246)"
              strokeOpacity="0.7"
              strokeWidth="1.5"
              points={history
                .map((item, i) => {
                  const x = (i / Math.max(history.length - 1, 1)) * 390 + 5;
                  const y =
                    90 -
                    ((Number(item.loss) - minLoss) /
                      Math.max(maxLoss - minLoss, 0.001)) *
                      80;
                  return `${x},${y}`;
                })
                .join(" ")}
            />
          </svg>
        )}
      </GlassPanel>
    </div>
  );
}

/* =========================================================
   NETWORK TAB
   ========================================================= */

function LegacyNetworkTab({ online }: { online: boolean }) {
  const [nodes, setNodes] = useState<NodeItem[]>([]);
  const [totalVram, setTotalVram] = useState(0);

  const [trainingActive, setTrainingActive] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!online) return;
    setLoading(true);
    try {
      const data = await apiCached<{
        nodes: NodeItem[];
        nodes_online: number;
        connected_users: number;
        total_vram_gb: number;
        training_active: boolean;
        workers_online: number;
      }>("/api/network", 4000);
      setNodes(data.nodes ?? []);
      setTotalVram(data.total_vram_gb ?? 0);
      setTrainingActive(data.training_active ?? false);
    } finally {
      setLoading(false);
    }
  }, [online]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!online) return;
    const t = setInterval(() => void load(), 5000);
    return () => clearInterval(t);
  }, [online, load]);

  const uniqueNodes = Array.from(new Map(nodes.map((n) => [n.id || n.name, n])).values());
  const onlineNodes = uniqueNodes.filter((n) => n.status === "online");
  const connectedUsers = Math.max(1, onlineNodes.filter((n) => !n.is_local).length + (onlineNodes.some((n) => n.is_local) ? 1 : 0));

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Header */}
      <div className="mb-4">
        <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
          WHO'S HELPING DOOF THINK
        </div>
        <div className="mt-1 text-[18px] font-semibold text-zinc-100">
          NETWORK
        </div>
        <div className="mt-1 text-[12px] leading-relaxed text-zinc-500">
          {onlineNodes.length > 0
            ? `${onlineNodes.length} NODE${onlineNodes.length === 1 ? "" : "S"} ONLINE · COMPUTE POOL ACTIVE`
            : "NO NODES ONLINE"}{" "}
          — distributed workers: each job runs on one node, not shared-gradient training.
        </div>
      </div>

      {/* Summary */}
      <div className="mb-3 grid grid-cols-3 gap-1.5">
        <MetricCard
          label="Nodes Online"
          value={onlineNodes.length}
          sub={`of ${uniqueNodes.length} registered`}
          accent
        />
        <MetricCard
          label="Connected Users"
          value={connectedUsers}
          sub="Trusted collaborators"
        />
        <MetricCard
          label="Total VRAM"
          value={`${totalVram.toFixed(1)} GB`}
        />
      </div>

      <div className="mb-3 grid grid-cols-2 gap-1.5">
        <MetricCard
          label="GPU Pool"
          value={onlineNodes.some((n) => n.gpu !== "CPU") ? "Hardware" : "CPU only"}
        />
        <MetricCard
          label="Training"
          value={trainingActive ? "Active" : "Idle"}
          sub={
            trainingActive
              ? nodes.find((n) => n.training_active)?.name ?? ""
              : undefined
          }
        />
      </div>

      {/* Node cards */}
      <div className="mb-2 text-[11px] uppercase tracking-[0.15em] text-zinc-500">
        Connected Nodes
      </div>
      <div className="space-y-1.5">
        {loading && nodes.length === 0 && (
          <div className="py-12 text-center text-[10px] text-zinc-800">Loading…</div>
        )}
        {uniqueNodes.map((node) => (
          <GlassPanel
            key={`${node.id}-${node.name}`}
            className="flex min-w-0 items-start justify-between gap-3 overflow-hidden p-3"
            glow={node.status === "online"}
          >
            <div className="flex min-w-0 items-start gap-3">
              <div
                className={[
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border text-[10px]",
                  node.status === "online"
                    ? "border-violet-400/15 bg-violet-500/[0.055] text-violet-400"
                    : "border-white/[0.04] bg-white/[0.01] text-zinc-700",
                ].join(" ")}
              >
                #
              </div>
              <div className="min-w-0">
                <div className="text-[14px] font-medium leading-snug text-zinc-200 break-words">
                  {node.name}
                  {node.is_local && (
                    <span className="ml-1.5 text-[10px] uppercase tracking-[0.12em] text-zinc-500">
                      (this machine)
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-[12px] leading-snug text-zinc-500 break-words">
                  {node.gpu || "CPU"} · {node.vram_gb > 0 ? `${node.vram_gb} GB VRAM` : (node.device || "cpu").toUpperCase()}
                </div>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <StatusBadge tone={node.status === "online" ? "online" : "danger"}>
                <StatusDot on={node.status === "online"} />
                {node.status === "online" ? "Online" : "Offline"}
              </StatusBadge>
              {node.training_active && (
                <StatusBadge tone="violet">Training</StatusBadge>
              )}
            </div>
          </GlassPanel>
        ))}
        {uniqueNodes.length === 0 && !loading && (
          <div className="rounded-xl border border-dashed border-white/[0.04] px-4 py-8 text-center text-[12px] text-zinc-500">
            No nodes registered. Your local machine will appear automatically.
          </div>
        )}
        {uniqueNodes.length === 1 && (
          <div className="mt-3 rounded-xl border border-dashed border-white/[0.06] px-4 py-3 text-[12px] leading-relaxed text-zinc-500">
            You are the only live node on this brain. Friends appear here when they
            join the same API host (Login → Join existing brain) or share the same
            Supabase project. A standalone EXE zip is its own network.
          </div>
        )}
      </div>

      {/* Architecture note */}
      <div className="mt-4 rounded-xl border border-white/[0.03] bg-white/[0.008] p-3 text-[12px] leading-relaxed text-zinc-500">
        <span className="text-zinc-700">How it works: </span>
        The strongest available node receives each training job. Compute is not
        distributed across nodes simultaneously — each job runs on one worker.
        Nodes register automatically and send heartbeats every 30 seconds.
      </div>
    </div>
  );
}

/* =========================================================
   MODELS TAB
   ========================================================= */

function ModelsTab({ online }: { online: boolean }) {
  const [ckpts, setCkpts] = useState<CheckpointItem[]>([]);
  const [modelInfo, setModelInfo] = useState<Data>({});

  const load = useCallback(async () => {
    if (!online) return;
    const [vers, info] = await Promise.all([
      apiCached<{ checkpoints: CheckpointItem[] }>("/api/models/versions", 20000),
      apiCached<Data>("/api/model", 20000),
    ]);
    setCkpts(vers.checkpoints ?? []);
    setModelInfo(info);
  }, [online]);

  useEffect(() => { void load(); }, [load]);

  const loadCkpt = async (path: string) => {
    await api("/api/model/load", { method: "POST", body: JSON.stringify({ path }) });
    void load();
  };

  const promote = async (name: string, label: string) => {
    await api("/api/models/promote", {
      method: "POST",
      body: JSON.stringify({ checkpoint_name: name, label }),
    });
    void load();
  };

  const production = ckpts.find((c) => c.status === "production");

  const statusBadge = (status: string) => {
    if (status === "production") return <StatusBadge tone="online">Production</StatusBadge>;
    if (status === "candidate") return <StatusBadge tone="violet">Candidate</StatusBadge>;
    return <StatusBadge tone="neutral">Archived</StatusBadge>;
  };

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Header */}
      <div className="mb-4">
        <div className="text-[12px] uppercase tracking-[0.18em] text-zinc-700">
          DOOF BRAIN VERSIONS
        </div>
      </div>

      {/* Current model stats */}
      <div className="mb-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        <MetricCard
          label="Parameters"
          value={
            modelInfo.parameters_m != null
              ? `${String(modelInfo.parameters_m)}M`
              : "—"
          }
          accent
        />
        <MetricCard label="Device" value={String(modelInfo.device ?? "—")} />
        <MetricCard label="d_model" value={String(modelInfo.d_model ?? "—")} />
        <MetricCard
          label="Status"
          value={modelInfo.loaded ? "Loaded" : "No model"}
        />
      </div>

      {/* Production brain */}
      {production && (
        <div className="mb-3">
          <div className="mb-1.5 text-[12px] uppercase tracking-[0.15em] text-zinc-700">
            Current Brain
          </div>
          <GlassPanel className="flex items-center justify-between p-3" glow>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[12px] font-semibold text-zinc-100">
                  {production.version_label ?? production.name}
                </span>
                {statusBadge("production")}
              </div>
              <div className="mt-0.5 text-[12px] text-zinc-600">
                {production.loss != null && `Loss ${Number(production.loss).toFixed(3)} · `}
                {production.size_mb != null && `${Number(production.size_mb).toFixed(1)} MB`}
                {production.step != null && ` · Step ${production.step}`}
              </div>
            </div>
            <GlassButton
              size="sm"
              variant="ghost"
              onClick={() => void loadCkpt(production.path)}
            >
              Reload
            </GlassButton>
          </GlassPanel>
        </div>
      )}

      {/* Version history */}
      <div className="mb-1.5 text-[12px] uppercase tracking-[0.15em] text-zinc-700">
        All Versions
      </div>
      <div className="space-y-1.5">
        {ckpts.length === 0 && (
          <div className="rounded-xl border border-white/[0.04] px-4 py-8 text-center text-[10px] text-zinc-800">
            No checkpoints found. Run training first.
          </div>
        )}
        {ckpts.map((ck) => (
          <div
            key={ck.name}
            className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.04] bg-white/[0.01] px-3 py-2 transition-all hover:border-white/[0.065]"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-[10px] text-zinc-300">{ck.name}</span>
                {statusBadge(ck.status)}
                {ck.loaded && (
                  <span className="text-[11px] uppercase tracking-[0.1em] text-emerald-400/60">
                    Active
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-[12px] text-zinc-700">
                {ck.loss != null && `Loss ${Number(ck.loss).toFixed(3)}`}
                {ck.size_mb != null && ` · ${Number(ck.size_mb).toFixed(1)} MB`}
                {ck.step != null && ` · Step ${ck.step}`}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <GlassButton
                size="sm"
                variant="ghost"
                onClick={() => void loadCkpt(ck.path)}
              >
                Load
              </GlassButton>
              {ck.status !== "production" && (
                <GlassButton
                  size="sm"
                  variant="success"
                  onClick={() =>
                    void promote(ck.name, ck.version_label ?? ck.name)
                  }
                >
                  Promote
                </GlassButton>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =========================================================
   SETTINGS TAB
   ========================================================= */

function SettingsTab({
  online,
  hw,
  onLogout,
}: {
  online: boolean;
  hw: HardwareInfo | null;
  onLogout?: () => void;
}) {
  const [sett, setSett] = useState({ temperature: 0.7, max_new_tokens: 80, top_k: 50 });
  const [cloud, setCloud] = useState<Data>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!online) return;
    Promise.all([
      api<typeof sett>("/api/settings"),
      api<Data>("/api/cloud"),
    ]).then(([s, c]) => {
      setSett(s);
      setCloud(c);
    }).catch(() => {});
  }, [online]);

  const save = async () => {
    await api("/api/settings", { method: "POST", body: JSON.stringify(sett) });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const SLIDERS: [keyof typeof sett, number, number, number][] = [
    ["temperature", 0.1, 2, 0.1],
    ["max_new_tokens", 16, 256, 8],
    ["top_k", 1, 100, 1],
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto max-w-lg space-y-5">
        {/* Inference */}
        <section>
          <div className="mb-2 text-[12px] uppercase tracking-[0.16em] text-zinc-700">
            Inference
          </div>
          <GlassPanel className="space-y-4 p-3.5">
            {SLIDERS.map(([key, min, max, step]) => (
              <label key={key} className="block">
                <div className="mb-1.5 flex justify-between text-[12px]">
                  <span className="text-zinc-600">{key.replace(/_/g, " ")}</span>
                  <span className="tabular-nums text-zinc-400">{sett[key]}</span>
                </div>
                <input
                  type="range"
                  min={min}
                  max={max}
                  step={step}
                  value={sett[key]}
                  onChange={(e) =>
                    setSett((cur) => ({
                      ...cur,
                      [key]:
                        key === "temperature"
                          ? parseFloat(e.target.value)
                          : parseInt(e.target.value, 10),
                    }))
                  }
                  className="w-full accent-violet-500"
                />
              </label>
            ))}
            <GlassButton onClick={() => void save()}>
              {saved ? "✓ Saved" : "Save settings"}
            </GlassButton>
          </GlassPanel>
        </section>

        {/* Hardware */}
        {hw && (
          <section>
            <div className="mb-2 text-[12px] uppercase tracking-[0.16em] text-zinc-700">
              Hardware
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <MetricCard label="Device" value={hw.device} />
              <MetricCard label="CUDA" value={hw.cuda_available ? "Available" : "No"} />
              {hw.cuda_devices[0] && (
                <>
                  <MetricCard label="GPU" value={hw.cuda_devices[0].name} />
                  <MetricCard label="VRAM" value={`${hw.cuda_devices[0].total_memory_gb} GB`} accent />
                </>
              )}
              <MetricCard label="Platform" value={hw.platform} />
              <MetricCard label="Python" value={hw.python ?? "—"} />
              <MetricCard label="Torch" value={hw.torch_version ?? "—"} />
              <MetricCard label="CPUs" value={String(hw.cpu_count ?? "—")} />
            </div>
          </section>
        )}

        {/* Cloud */}
        <section>
          <div className="mb-2 text-[12px] uppercase tracking-[0.16em] text-zinc-700">
            Cloud / Supabase
          </div>
          <GlassPanel className="flex items-center gap-2 p-3">
            <StatusDot on={Boolean(cloud.connected)} />
            <span className="text-[12px] text-zinc-600">
              {String(cloud.message ?? cloud.status ?? "Local mode · offline only")}
            </span>
          </GlassPanel>
          <div className="mt-1.5 text-[12px] text-zinc-800">
            Set SUPABASE_URL and SUPABASE_ANON_KEY to enable cloud sync. Local mode still works.
          </div>
        </section>

        {/* Ambient */}
        <section>
          <div className="mb-2 text-[12px] uppercase tracking-[0.16em] text-zinc-700">
            Ambient
          </div>
          <GlassPanel className="flex items-center justify-between gap-3 p-3">
            <div className="text-[12px] text-zinc-600">
              Quiet Arabic rap · loops after sign-in
            </div>
            <MusicControl />
          </GlassPanel>
        </section>

        {/* Account */}
        {onLogout && (
          <section>
            <div className="mb-2 text-[12px] uppercase tracking-[0.16em] text-zinc-700">Account</div>
            <GlassButton variant="danger" onClick={onLogout}>
              Sign out
            </GlassButton>
          </section>
        )}

        {/* About */}
        <section>
          <div className="mb-2 text-[12px] uppercase tracking-[0.16em] text-zinc-700">About</div>
          <GlassPanel className="p-3.5 text-[12px] leading-relaxed text-zinc-700">
            DOOF v0.2 Alpha · decoder-only Transformer · local-first private AI OS
            <br />
            Fueled by Big Ol&apos; Rusty Tuna Cans, Shawarmas and Red Bull.
            <br />
            Intelligence: memory, RAG, quality scoring, dataset builder, evaluation
            <br />
            Compute: job-level pool · one job, one node · never silent remote use
            <br />
            Fueled by shawarmas, Lebanon, and the occasional rusty tuna can.
          </GlassPanel>
        </section>
      </div>
    </div>
  );
}


/* =========================================================
   MUSIC CONTROL (ambient — auth-gated via doofAudio)
   ========================================================= */

function MusicControl() {
  const [muted, setMuted] = useState(doofAudio.isMuted());
  const [vol, setVol] = useState(doofAudio.getVolume());

  useEffect(() => {
    return doofAudio.subscribe((s) => {
      setMuted(s.muted);
      setVol(s.volume);
    });
  }, []);

  return (
    <div className="flex items-center gap-1.5" title="Ambient track">
      <button
        type="button"
        onClick={() => doofAudio.toggleMute()}
        className={[
          "rounded-lg border px-1.5 py-0.5 text-[12px] transition-all",
          muted
            ? "border-white/[0.05] bg-white/[0.015] text-zinc-600 hover:text-zinc-400"
            : "border-violet-400/20 bg-violet-500/[0.08] text-violet-300/90",
        ].join(" ")}
        aria-label={muted ? "Unmute ambient" : "Mute ambient"}
      >
        {muted ? "MUTE" : "DOOF FM"}
      </button>
      <input
        type="range"
        min={0}
        max={0.18}
        step={0.005}
        value={muted ? 0 : vol}
        onChange={(e) => doofAudio.setVolume(parseFloat(e.target.value))}
        className="h-1 w-14 accent-violet-500"
        aria-label="Ambient volume"
      />
    </div>
  );
}

/* =========================================================
   TOP BAR
   ========================================================= */

function TopBar({
  page,
  online,
  hw,
  err,
}: {
  page: Page;
  online: boolean;
  hw: HardwareInfo | null;
  err: string;
}) {
  const cudaOn = hw?.cuda_available ?? false;
  return (
    <header className="flex h-[38px] shrink-0 items-center justify-between border-b border-white/[0.045] bg-[#000000]/96 px-4 backdrop-blur-xl">
      <div className="text-[12px] font-medium uppercase tracking-[0.17em] text-zinc-700">
        DOOF · {page}
      </div>
      <div className="flex items-center gap-1.5">
        <MusicControl />
        {err && (
          <span className="max-w-[200px] truncate text-[12px] text-rose-400/70">{err}</span>
        )}
        <StatusBadge tone={online ? "online" : "neutral"}>
          <StatusDot on={online} />
          {online ? "Local" : "Offline"}
        </StatusBadge>
        {cudaOn && <StatusBadge tone="violet">CUDA</StatusBadge>}
      </div>
    </header>
  );
}

/* =========================================================
   ROOT APP
   ========================================================= */

/* =========================================================
   HARDWARE TAB
   ========================================================= */

function LegacyHardwareTab({ hw, online }: { hw: HardwareInfo | null; online: boolean }) {
  const gpus = hw?.cuda_devices ?? [];
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-[13px] font-semibold text-zinc-200">Hardware</span>
        <StatusBadge tone={online ? "online" : "neutral"}>
          <StatusDot on={online} />
          {online ? "Reporting" : "Offline"}
        </StatusBadge>
      </div>
      {!hw ? (
        <div className="rounded-xl border border-white/[0.04] px-4 py-8 text-center text-[10px] text-zinc-800">
          Waiting for hardware report…
        </div>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            <MetricCard label="Device" value={hw.device.toUpperCase()} accent />
            <MetricCard label="Platform" value={hw.platform} sub={hw.machine} />
            <MetricCard label="CPU Cores" value={hw.cpu_count ?? "—"} />
            <MetricCard label="Torch" value={hw.torch_version ?? "—"} />
          </div>
          <div className="mb-1.5 text-[12px] uppercase tracking-[0.15em] text-zinc-700">GPUs</div>
          {gpus.length === 0 ? (
            <div className="rounded-xl border border-white/[0.04] px-4 py-6 text-center text-[10px] text-zinc-800">
              No CUDA GPU detected{hw.mps_available ? " · Apple MPS available" : ""} — training
              will run on CPU.
            </div>
          ) : (
            <div className="space-y-1.5">
              {gpus.map((g, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-xl border border-white/[0.04] bg-white/[0.01] px-3 py-2"
                >
                  <span className="text-[10px] text-zinc-300">{g.name}</span>
                  <span className="text-[12px] tabular-nums text-violet-300/80">
                    {g.total_memory_gb} GB VRAM
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function App() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [page, setPage] = useState<Page>("chat");
  const [online, setOnline] = useState(false);
  const [hw, setHw] = useState<HardwareInfo | null>(null);
  const [err, setErr] = useState("");
  const [booted, setBooted] = useState(false);

  // Chat state
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sett] = useState({ temperature: 0.7, max_new_tokens: 80, top_k: 50 });
  const [trainRunning, setTrainRunning] = useState(false);
  // 'verifying' | 'verified' | 'error' | null (email confirmation landing)
  const [verifyState, setVerifyState] = useState<"verifying" | "verified" | "error" | null>(null);
  const [verifyMsg, setVerifyMsg] = useState("");

  // Validate stored session / handle OAuth + email-verification redirects
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const hash = window.location.hash;

    // --- Email verification link (?token=...&type=signup or #token=...) ---
    const vt =
      params.get("token") ||
      params.get("token_hash") ||
      hash.match(/[?&]token_hash=([^&]+)/)?.[1] ||
      hash.match(/[?&]token=([^&]+)/)?.[1] ||
      hash.match(/[#?]token=([^&]+)/)?.[1];
    const vtype = params.get("type") || "signup";
    if (vt) {
      history.replaceState(null, "", window.location.pathname);
      setVerifyState("verifying");
      fetch(`${serverBase()}/api/auth/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: decodeURIComponent(vt), token_hash: decodeURIComponent(vt), type: vtype }),
      })
        .then((r) => r.json())
        .then((d: { token?: string; profile?: Profile; error?: string; status?: string }) => {
          if (d.token && d.profile) {
            storeToken(d.token, true);
            setVerifyState(null); // verified + session → enter DOOF directly
            setProfile(d.profile);
          } else if (d.status === "already_verified") {
            setVerifyState("verified");
          } else {
            setVerifyState("error");
            setVerifyMsg(
              d.error || "This verification link is invalid or has expired — request a new one.",
            );
          }
        })
        .catch(() => {
          setVerifyState("error");
          setVerifyMsg("Couldn't reach the DOOF brain to verify your email.");
        });
      return;
    }

    // --- Google OAuth (Supabase implicit flow) returned to us ---
    const m = hash.match(/access_token=([^&]+)/);
    if (m) {
      history.replaceState(null, "", window.location.pathname);
      fetch(`${serverBase()}/api/auth/oauth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_token: decodeURIComponent(m[1]) }),
      })
        .then((r) => r.json())
        .then((d: { token?: string; profile?: Profile; error?: string }) => {
          if (d.token && d.profile) {
            storeToken(d.token, true);
            setProfile(d.profile);
          } else {
            setProfile(null);
          }
        })
        .catch(() => setProfile(null));
      return;
    }

    const token = getToken();
    if (!token) {
      setProfile(null);
      return;
    }
    api<{ profile: Profile | null }>("/api/me")
      .then((d) => setProfile(d.profile ?? null))
      .catch(() => setProfile(null));
  }, []);

  const doLogout = useCallback(async () => {
    doofAudio.stop();
    try {
      await api("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
    } catch { /* ignore */ }
    clearToken();
    setProfile(null);
  }, []);

  // Ambient music — only while authenticated (never on login screen)
  useEffect(() => {
    if (profile) {
      doofAudio.start();
      return () => {
        doofAudio.stop();
      };
    }
    doofAudio.stop();
  }, [profile]);

  const inputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Health + hardware — parallel, cached; heartbeat lives server-side
  const ping = useCallback(async () => {
    try {
      await api("/api/health");
      setOnline(true);
      setErr("");
      const cachedHw = cacheGet<HardwareInfo>("/api/hardware");
      if (cachedHw) setHw(cachedHw);
      void api<HardwareInfo>("/api/hardware")
        .then((hwData) => {
          cacheSet("/api/hardware", hwData);
          setHw(hwData);
          void api("/api/nodes/register", {
            method: "POST",
            body: JSON.stringify({
              gpu: hwData.cuda_devices?.[0]?.name || (hwData.cuda_available ? "CUDA" : "CPU"),
              vram_gb: hwData.cuda_devices?.[0]?.total_memory_gb || 0,
              device: hwData.device || "cpu",
              cuda_available: Boolean(hwData.cuda_available),
              platform: hwData.platform,
              torch_version: hwData.torch_version,
            }),
          }).catch(() => {});
        })
        .catch(() => {});
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    void ping();
    const t = setInterval(() => void ping(), 15000);
    return () => clearInterval(t);
  }, [ping]);

  // Training status — adaptive: fast while training, relaxed when idle
  useEffect(() => {
    if (!online) return;
    let stop = false;
    const tick = async () => {
      try {
        const d = await api<{ running: boolean }>("/api/training");
        if (stop) return;
        setTrainRunning(d.running ?? false);
        schedule((d.running ?? false) ? 2500 : 12000);
      } catch {
        if (!stop) schedule(15000);
      }
    };
    const timer = { id: 0 as ReturnType<typeof setInterval> | ReturnType<typeof setTimeout> };
    const schedule = (ms: number) => {
      clearTimeout(timer.id);
      timer.id = setTimeout(() => void tick(), ms);
    };
    void tick();
    return () => {
      stop = true;
      clearTimeout(timer.id);
    };
  }, [online]);

  // Auto-scroll chat
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs]);

  // ---- Auth gate -------------------------------------------------------
  if (!booted) {
    return <Boot apiBase={serverBase()} onDone={() => setBooted(true)} />;
  }

  if (verifyState === "verifying") {
    return (
      <div className="relative h-screen w-screen overflow-hidden bg-[#030304] text-zinc-300">
        <NaddafAtmosphere />
        <div className="relative z-10 flex h-full items-center justify-center">
          <div className="doof-fade flex flex-col items-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/[0.07] text-[16px] text-violet-300 doof-pulse">
              D
            </div>
            <div className="mt-3 text-[13px] font-semibold text-zinc-100">Verifying email…</div>
            <div className="mt-1 text-[12px] text-zinc-500">Confirming with the DOOF brain.</div>
          </div>
        </div>
      </div>
    );
  }

  if (verifyState === "verified") {
    return (
      <div className="relative h-screen w-screen overflow-hidden bg-[#030304] text-zinc-300">
        <NaddafAtmosphere />
        <div className="relative z-10 flex h-full items-center justify-center">
          <div className="doof-fade w-full max-w-[340px] rounded-3xl border border-white/[0.06] bg-[#09090b]/92 p-6 text-center shadow-[0_20px_70px_rgba(0,0,0,0.5)] backdrop-blur-md">
            <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-500/[0.07] text-[16px] text-emerald-300">
              ✓
            </div>
            <h1 className="mt-3 text-[15px] font-semibold tracking-tight text-zinc-100">
              EMAIL VERIFIED
            </h1>
            <p className="mt-1.5 text-[10px] leading-relaxed text-zinc-400">
              You're in. Entering DOOF now.
            </p>
            {!profile && (
              <button
                type="button"
                onClick={() => {
                  setVerifyState(null);
                  setProfile(null);
                }}
                className="mt-4 w-full rounded-xl border border-violet-400/20 bg-violet-600/70 py-2 text-[10px] font-medium text-white transition hover:bg-violet-500"
              >
                Sign in
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (verifyState === "error") {
    return (
      <div className="relative h-screen w-screen overflow-hidden bg-[#030304] text-zinc-300">
        <NaddafAtmosphere />
        <div className="relative z-10 flex h-full items-center justify-center">
          <div className="doof-fade w-full max-w-[340px] rounded-3xl border border-white/[0.06] bg-[#09090b]/92 p-6 text-center shadow-[0_20px_70px_rgba(0,0,0,0.5)] backdrop-blur-md">
            <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-rose-400/20 bg-rose-500/[0.07] text-[16px] text-rose-300">
              !
            </div>
            <h1 className="mt-3 text-[15px] font-semibold tracking-tight text-zinc-100">
              VERIFICATION FAILED
            </h1>
            <p className="mt-1.5 text-[10px] leading-relaxed text-zinc-400">{verifyMsg}</p>
            <button
              type="button"
              onClick={() => {
                setVerifyState(null);
                setProfile(null);
              }}
              className="mt-4 w-full rounded-xl border border-violet-400/20 bg-violet-600/70 py-2 text-[10px] font-medium text-white transition hover:bg-violet-500"
            >
              Back to sign in
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (profile === undefined) {
    return <div className="h-screen w-screen bg-[#030304]" />;
  }

  if (profile === null) {
    return (
      <div className="relative h-screen w-screen overflow-hidden bg-[#030304] text-zinc-300">
        <NaddafAtmosphere />
        <div className="relative z-10 flex h-full items-center justify-center overflow-y-auto">
          <Login onLogin={setProfile} />
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#030304] text-zinc-300 selection:bg-violet-500/25">
      <style>{`
        @keyframes doof-star {
          0% { opacity: 0.04; transform: translate3d(0,0,0); }
          100% { opacity: 0.26; transform: translate3d(3px,-2px,0); }
        }
        @keyframes doof-pulse {
          0%, 100% { opacity: .5; }
          50% { opacity: 1; }
        }
        .doof-pulse { animation: doof-pulse 1.8s ease-in-out infinite; }
        * { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,.05) transparent; }
        *::-webkit-scrollbar { width: 4px; height: 4px; }
        *::-webkit-scrollbar-track { background: transparent; }
        *::-webkit-scrollbar-thumb { background: rgba(255,255,255,.05); border-radius: 999px; }
        *::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,.09); }
      `}</style>

      <NaddafAtmosphere />

      <div className="relative z-10 flex h-full">
        <Sidebar
          page={page}
          setPage={setPage}
          online={online}
          hw={hw}
          trainRunning={trainRunning}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          <TopBar page={page} online={online} hw={hw} err={err} />

          <div className="mx-auto flex min-h-0 w-full max-w-[900px] flex-1 flex-col">
            {page === "chat" && (
              <ChatTab
                msgs={msgs}
                setMsgs={setMsgs}
                input={input}
                setInput={setInput}
                busy={busy}
                setBusy={setBusy}
                online={online}
                sett={sett}
                inputRef={inputRef}
                bottomRef={bottomRef}
              />
            )}
            {page === "memory" && <MemoryTab online={online} />}
            {page === "training" && <TrainingTab online={online} />}
            {page === "status" && <StatusTab online={online} />}
            {page === "models" && <ModelsTab online={online} />}
            {page === "settings" && (
              <SettingsTab online={online} hw={hw} onLogout={() => void doLogout()} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export { LegacyNetworkTab, LegacyHardwareTab };
