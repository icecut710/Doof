import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Page =
  | "chat"
  | "knowledge"
  | "training"
  | "models"
  | "hardware"
  | "settings";

type Msg = {
  role: "user" | "doof";
  text: string;
  pending?: boolean;
};

type Data = Record<string, unknown>;

const API = "http://127.0.0.1:8765";

const NAV: {
  id: Page;
  label: string;
  icon: string;
  section: string;
}[] = [
  { id: "chat", label: "Chat", icon: "◆", section: "DOOF" },
  { id: "knowledge", label: "Knowledge", icon: "◇", section: "DOOF" },
  { id: "training", label: "Training", icon: "↯", section: "LEARN" },
  { id: "models", label: "Models", icon: "◈", section: "SYSTEM" },
  { id: "hardware", label: "Hardware", icon: "▣", section: "SYSTEM" },
  { id: "settings", label: "Settings", icon: "⚙", section: "SYSTEM" },
];

const SUGGESTIONS = [
  "What have you learned?",
  "Tell me about yourself",
  "What is my training status?",
  "Generate something",
];

async function api<T = Data>(
  path: string,
  opts?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts?.headers || {}),
    },
  });

  const json = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      (json as { error?: string }).error ||
        response.statusText ||
        "Request failed",
    );
  }

  return json as T;
}

/* =========================================================
   DESIGN ATOMS
   ========================================================= */

function StatusDot({ on }: { on: boolean }) {
  return (
    <span
      className={[
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
        on
          ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
          : "bg-zinc-700",
      ].join(" ")}
    />
  );
}

function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "violet";
}) {
  const toneClass =
    tone === "ok"
      ? "border-emerald-400/15 bg-emerald-400/[0.045] text-emerald-400/90"
      : tone === "violet"
        ? "border-violet-400/20 bg-violet-500/[0.065] text-violet-300/90"
        : "border-white/[0.065] bg-white/[0.018] text-zinc-500";

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5",
        "rounded-full border",
        "px-2 py-1",
        "text-[8px] uppercase tracking-[0.13em]",
        "shadow-[0_2px_12px_rgba(0,0,0,0.16)]",
        toneClass,
      ].join(" ")}
    >
      {children}
    </span>
  );
}

function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={[
        "rounded-2xl border border-white/[0.055]",
        "bg-[#080809]/90",
        "shadow-[0_8px_30px_rgba(0,0,0,0.18)]",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      className="
        rounded-xl
        border border-white/[0.045]
        bg-white/[0.012]
        px-3
        py-2.5
        shadow-[0_4px_18px_rgba(0,0,0,0.12)]
      "
    >
      <div className="text-[8px] font-medium uppercase tracking-[0.14em] text-zinc-700">
        {label}
      </div>

      <div className="mt-1 truncate text-[12px] font-medium tracking-tight text-zinc-300">
        {value}
      </div>
    </div>
  );
}

function Btn({
  children,
  onClick,
  disabled,
  variant = "primary",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
}) {
  const styles =
    variant === "primary"
      ? [
          "border-violet-400/20",
          "bg-violet-600/80",
          "text-white",
          "shadow-[0_4px_18px_rgba(124,58,237,0.16)]",
          "hover:bg-violet-500",
          "hover:border-violet-300/25",
        ].join(" ")
      : variant === "danger"
        ? [
            "border-rose-500/20",
            "bg-rose-500/[0.08]",
            "text-rose-300",
            "hover:bg-rose-500/[0.14]",
          ].join(" ")
        : [
            "border-white/[0.07]",
            "bg-white/[0.018]",
            "text-zinc-500",
            "hover:bg-white/[0.04]",
            "hover:text-zinc-300",
          ].join(" ");

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "rounded-xl border px-3.5 py-1.5",
        "text-[10px] font-medium",
        "transition-all duration-200",
        "disabled:cursor-not-allowed disabled:opacity-30",
        styles,
      ].join(" ")}
    >
      {children}
    </button>
  );
}

/* =========================================================
   STAR FIELD
   ========================================================= */

function StarField() {
  const stars = useMemo(() => {
    return Array.from({ length: 70 }, (_, i) => ({
      left: `${(i * 19.37) % 100}%`,
      top: `${(i * 37.13 + 4) % 100}%`,
      size: i % 11 === 0 ? 1.5 : 1,
      opacity: 0.08 + ((i * 17) % 22) / 100,
      delay: `${(i % 8) * 0.55}s`,
      duration: `${6 + (i % 6)}s`,
    }));
  }, []);

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden"
      aria-hidden
    >
      {stars.map((star, i) => (
        <span
          key={i}
          className="absolute rounded-full bg-white"
          style={{
            left: star.left,
            top: star.top,
            width: star.size,
            height: star.size,
            opacity: star.opacity,
            animation: `doof-star ${star.duration} ease-in-out ${star.delay} infinite alternate`,
          }}
        />
      ))}
    </div>
  );
}

/* =========================================================
   MR NADDAF ATMOSPHERE
   ========================================================= */

function NaddafAtmosphere() {
  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden"
      aria-hidden
    >
      <StarField />

      {/* Large centered Naddaf image */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className="
            absolute
            left-1/2
            top-1/2
            h-[94%]
            w-[94%]
            -translate-x-1/2
            -translate-y-1/2
          "
          style={{
            WebkitMaskImage:
              "radial-gradient(ellipse 72% 70% at 50% 50%, black 8%, rgba(0,0,0,.98) 34%, rgba(0,0,0,.82) 63%, rgba(0,0,0,.38) 82%, transparent 100%)",
            maskImage:
              "radial-gradient(ellipse 72% 70% at 50% 50%, black 8%, rgba(0,0,0,.98) 34%, rgba(0,0,0,.82) 63%, rgba(0,0,0,.38) 82%, transparent 100%)",
          }}
        >
          <img
            src="/mrnaddaf.png"
            alt=""
            draggable={false}
            className="
              h-full
              w-full
              object-contain
              object-center
              grayscale
              contrast-[1.12]
              brightness-[0.86]
              opacity-[0.58]
              mix-blend-screen
            "
          />
        </div>
      </div>

      {/* Large soft center illumination */}
      <div
        className="
          absolute
          left-1/2
          top-1/2
          h-[520px]
          w-[520px]
          -translate-x-1/2
          -translate-y-1/2
          rounded-full
          bg-violet-600/[0.055]
          blur-[150px]
        "
      />

      {/* Keep the center readable without killing the artwork */}
      <div
        className="
          absolute
          inset-0
          bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(3,3,4,.08)_42%,rgba(3,3,4,.58)_100%)]
        "
      />

      {/* Very subtle center veil */}
      <div
        className="
          absolute
          inset-0
          bg-[radial-gradient(ellipse_42%_48%_at_50%_48%,rgba(3,3,4,.02),rgba(3,3,4,.46)_100%)]
        "
      />

      {/* Cinematic top/bottom edges */}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/75 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-black/88 to-transparent" />

      {/* Side falloff */}
      <div className="absolute inset-y-0 left-0 w-40 bg-gradient-to-r from-[#030304]/90 to-transparent" />
      <div className="absolute inset-y-0 right-0 w-40 bg-gradient-to-l from-[#030304]/65 to-transparent" />
    </div>
  );
}

/* =========================================================
   APP
   ========================================================= */

export default function App() {
  const [page, setPage] = useState<Page>("chat");
  const [online, setOnline] = useState(false);

  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const [know, setKnow] = useState("");
  const [knowQuery, setKnowQuery] = useState("");

  const [train, setTrain] = useState<Data>({});
  const [model, setModel] = useState<Data>({});
  const [ckpts, setCkpts] = useState<Data[]>([]);
  const [hw, setHw] = useState<Data>({});

  const [sett, setSett] = useState({
    temperature: 0.7,
    max_new_tokens: 80,
    top_k: 50,
  });

  const [cloud, setCloud] = useState<Data>({});
  const [err, setErr] = useState("");

  const bottom = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /* -------------------------------------------------------
     HEALTH
     ------------------------------------------------------- */

  const ping = useCallback(async () => {
    try {
      await api("/api/health");
      setOnline(true);
      setErr("");
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    void ping();

    const timer = window.setInterval(() => {
      void ping();
    }, 4000);

    return () => window.clearInterval(timer);
  }, [ping]);

  /* -------------------------------------------------------
     AUTO SCROLL
     ------------------------------------------------------- */

  useEffect(() => {
    bottom.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [msgs]);

  /* -------------------------------------------------------
     PAGE DATA
     ------------------------------------------------------- */

  const refreshPage = useCallback(async () => {
    if (!online) return;

    try {
      if (page === "knowledge") {
        const data = await api<{ text?: string }>(
          "/api/knowledge",
        );

        setKnow(data.text || "");
      }

      if (page === "training") {
        setTrain(await api("/api/training"));
      }

      if (page === "models") {
        setModel(await api("/api/model"));

        const data = await api<{
          checkpoints?: Data[];
        }>("/api/checkpoints");

        setCkpts(data.checkpoints || []);
      }

      if (page === "hardware") {
        setHw(await api("/api/hardware"));
      }

      if (page === "settings") {
        setSett(
          (await api("/api/settings")) as typeof sett,
        );

        setCloud(await api("/api/cloud"));
      }

      if (page === "chat") {
        try {
          setModel(await api("/api/model"));
          setHw(await api("/api/hardware"));
        } catch {
          // optional
        }
      }
    } catch (error) {
      setErr(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  }, [page, online]);

  useEffect(() => {
    void refreshPage();
  }, [refreshPage]);

  /* -------------------------------------------------------
     TRAINING POLL
     ------------------------------------------------------- */

  useEffect(() => {
    if (page !== "training" || !online) return;

    const timer = window.setInterval(async () => {
      try {
        setTrain(await api("/api/training"));
      } catch {
        // ignore polling errors
      }
    }, 1400);

    return () => window.clearInterval(timer);
  }, [page, online]);

  /* -------------------------------------------------------
     CHAT
     ------------------------------------------------------- */

  const send = async (override?: string) => {
    const text = (override ?? input).trim();

    if (!text || busy || !online) return;

    if (!override) {
      setInput("");
    }

    setMsgs((current) => [
      ...current,
      {
        role: "user",
        text,
      },
      {
        role: "doof",
        text: "…",
        pending: true,
      },
    ]);

    setBusy(true);

    try {
      const data = await api<{ text?: string }>(
        "/api/generate",
        {
          method: "POST",
          body: JSON.stringify({
            prompt: text,
            temperature: sett.temperature,
            max_new_tokens: sett.max_new_tokens,
            top_k: sett.top_k,
          }),
        },
      );

      const output =
        data.text?.trim() || "(empty response)";

      setMsgs((current) => {
        const next = [...current];
        const last = next.length - 1;

        if (last >= 0 && next[last].pending) {
          next[last] = {
            role: "doof",
            text: output,
          };
        }

        return next;
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : String(error);

      setMsgs((current) => {
        const next = [...current];
        const last = next.length - 1;

        if (last >= 0 && next[last].pending) {
          next[last] = {
            role: "doof",
            text: `Error: ${message}`,
          };
        }

        return next;
      });
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  /* -------------------------------------------------------
     KNOWLEDGE
     ------------------------------------------------------- */

  const saveKnow = async () => {
    try {
      await api("/api/knowledge", {
        method: "POST",
        body: JSON.stringify({
          text: know,
        }),
      });

      setErr("");
    } catch (error) {
      setErr(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  };

  /* -------------------------------------------------------
     TRAINING
     ------------------------------------------------------- */

  const startTrain = async () => {
    try {
      await api("/api/training/start", {
        method: "POST",
        body: JSON.stringify({
          epochs: 3,
        }),
      });

      setTrain(await api("/api/training"));
    } catch (error) {
      setErr(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  };

  const stopTrain = async () => {
    try {
      await api("/api/training/stop", {
        method: "POST",
        body: JSON.stringify({}),
      });
    } catch (error) {
      setErr(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  };

  /* -------------------------------------------------------
     MODELS
     ------------------------------------------------------- */

  const loadCkpt = async (path: string) => {
    try {
      await api("/api/model/load", {
        method: "POST",
        body: JSON.stringify({ path }),
      });

      setModel(await api("/api/model"));
      setErr("");
    } catch (error) {
      setErr(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  };

  /* -------------------------------------------------------
     SETTINGS
     ------------------------------------------------------- */

  const saveSett = async () => {
    try {
      await api("/api/settings", {
        method: "POST",
        body: JSON.stringify(sett),
      });

      setErr("");
    } catch (error) {
      setErr(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  };

  /* -------------------------------------------------------
     DERIVED
     ------------------------------------------------------- */

  const sections = ["DOOF", "LEARN", "SYSTEM"];

  const history =
    (train.history as {
      step?: number;
      loss?: number;
    }[]) || [];

  const deviceLabel = String(
    hw.device ||
      model.device ||
      "LOCAL",
  );

  const cudaOn = Boolean(
    hw.cuda_available,
  );

  const ckptName =
    String(model.checkpoint || "")
      .split(/[/\\]/)
      .pop() || "—";

  const knowLines = know
    .split("\n")
    .filter((line) => line.trim());

  const filteredKnow = knowQuery
    ? knowLines.filter((line) =>
        line
          .toLowerCase()
          .includes(knowQuery.toLowerCase()),
      )
    : knowLines;

  return (
    <div
      className="
        relative
        h-screen
        w-screen
        overflow-hidden
        bg-[#030304]
        text-zinc-300
        selection:bg-violet-500/25
      "
    >
      <style>{`
        @keyframes doof-star {
          0% {
            opacity: 0.05;
            transform: translate3d(0, 0, 0);
          }

          100% {
            opacity: 0.28;
            transform: translate3d(3px, -2px, 0);
          }
        }

        @keyframes doof-pulse {
          0%, 100% {
            opacity: .55;
          }

          50% {
            opacity: 1;
          }
        }

        .doof-pulse {
          animation: doof-pulse 2.4s ease-in-out infinite;
        }

        * {
          scrollbar-width: thin;
          scrollbar-color: rgba(255,255,255,.06) transparent;
        }

        *::-webkit-scrollbar {
          width: 5px;
          height: 5px;
        }

        *::-webkit-scrollbar-track {
          background: transparent;
        }

        *::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,.06);
          border-radius: 999px;
        }

        *::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,.10);
        }
      `}</style>

      <NaddafAtmosphere />

      <div className="relative z-10 flex h-full">
        {/* =================================================
            SIDEBAR
            ================================================= */}

        <aside
          className="
            flex
            w-[166px]
            shrink-0
            flex-col
            border-r
            border-white/[0.045]
            bg-[#030304]/95
            backdrop-blur-xl
          "
        >
          {/* Logo */}
          <div
            className="
              flex
              h-[50px]
              shrink-0
              items-center
              gap-2.5
              border-b
              border-white/[0.045]
              px-3
            "
          >
            <div
              className="
                flex
                h-7
                w-7
                items-center
                justify-center
                rounded-[10px]
                border
                border-violet-400/20
                bg-violet-500/[0.065]
                text-[10px]
                font-bold
                text-violet-300
                shadow-[0_0_18px_rgba(124,58,237,0.08)]
              "
            >
              D
            </div>

            <div>
              <div className="text-[11px] font-semibold tracking-tight text-zinc-100">
                DOOF
              </div>

              <div className="text-[7px] uppercase tracking-[0.16em] text-zinc-700">
                v0.1 · local
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-2 py-2.5">
            {sections.map((section) => (
              <div
                key={section}
                className="mb-3.5"
              >
                <div
                  className="
                    mb-1
                    px-2
                    text-[7px]
                    font-medium
                    uppercase
                    tracking-[0.2em]
                    text-zinc-800
                  "
                >
                  {section}
                </div>

                {NAV.filter(
                  (item) =>
                    item.section === section,
                ).map((item) => {
                  const active =
                    page === item.id;

                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() =>
                        setPage(item.id)
                      }
                      className={[
                        "mb-0.5 flex w-full items-center gap-2",
                        "rounded-xl px-2 py-1.5 text-left",
                        "text-[10px] transition-all duration-200",
                        active
                          ? [
                              "bg-violet-500/[0.11]",
                              "text-violet-200",
                              "shadow-[inset_0_0_0_1px_rgba(139,92,246,0.16),0_4px_16px_rgba(0,0,0,0.12)]",
                            ].join(" ")
                          : [
                              "text-zinc-600",
                              "hover:bg-white/[0.025]",
                              "hover:text-zinc-400",
                            ].join(" "),
                      ].join(" ")}
                    >
                      <span
                        className={[
                          "w-3.5 text-center text-[8px]",
                          active
                            ? "text-violet-400"
                            : "text-zinc-800",
                        ].join(" ")}
                      >
                        {item.icon}
                      </span>

                      {item.label}
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>

          {/* Status */}
          <div
            className="
              shrink-0
              border-t
              border-white/[0.045]
              px-2.5
              py-2.5
            "
          >
            <div className="flex items-center gap-1.5">
              <StatusDot on={online} />

              <span className="text-[8px] uppercase tracking-[0.13em] text-zinc-600">
                {online ? "Local" : "Offline"}
              </span>
            </div>

            <div className="mt-1 truncate text-[8px] uppercase text-zinc-800">
              {deviceLabel}
              {cudaOn ? " · CUDA" : ""}
            </div>

            <div
              className="
                mt-0.5
                truncate
                text-[8px]
                text-zinc-800
              "
              title={ckptName}
            >
              {ckptName}
            </div>
          </div>
        </aside>

        {/* =================================================
            MAIN
            ================================================= */}

        <main className="flex min-w-0 flex-1 flex-col">
          {/* TOP BAR */}
          <header
            className="
              flex
              h-[40px]
              shrink-0
              items-center
              justify-between
              border-b
              border-white/[0.045]
              bg-[#000000]/95
              px-4
              backdrop-blur-xl
            "
          >
            <div
              className="
                text-[8px]
                font-medium
                uppercase
                tracking-[0.17em]
                text-zinc-700
              "
            >
              DOOF / {page}
            </div>

            <div className="flex items-center gap-1.5">
              {err && (
                <span className="max-w-[220px] truncate text-[8px] text-rose-400/70">
                  {err}
                </span>
              )}

              <Pill
                tone={
                  online
                    ? "ok"
                    : "neutral"
                }
              >
                <StatusDot on={online} />

                {online
                  ? "Local"
                  : "Offline"}
              </Pill>

              {cudaOn && (
                <Pill tone="violet">
                  CUDA
                </Pill>
              )}
            </div>
          </header>

          {/* CONTENT */}
          <div className="flex min-h-0 flex-1 flex-col">
            {/* =================================================
                CHAT
                ================================================= */}

            {page === "chat" && (
              <>
                <div className="relative flex-1 overflow-hidden">
                  <div className="absolute inset-0 overflow-y-auto px-4 py-3">
                    {msgs.length === 0 ? (
                      <div className="flex min-h-full items-center justify-center">
                        <div
                          className="
                            relative
                            z-10
                            -mt-5
                            w-full
                            max-w-[390px]
                            text-center
                          "
                        >
                          {/* Small logo */}
                          <div
                            className="
                              mx-auto
                              flex
                              h-9
                              w-9
                              items-center
                              justify-center
                              rounded-[12px]
                              border
                              border-violet-400/15
                              bg-violet-500/[0.055]
                              text-[13px]
                              font-semibold
                              text-violet-300/85
                              shadow-[0_0_24px_rgba(124,58,237,0.08)]
                            "
                          >
                            D
                          </div>

                          <h1
                            className="
                              mt-2.5
                              text-[18px]
                              font-semibold
                              tracking-[-0.035em]
                              text-zinc-200
                            "
                          >
                            DOOF
                          </h1>

                          <p className="mt-0.5 text-[9px] text-zinc-700">
                            Your local intelligence.
                          </p>

                          {/* Status */}
                          <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                            <Pill
                              tone={
                                online
                                  ? "ok"
                                  : "neutral"
                              }
                            >
                              <StatusDot
                                on={online}
                              />

                              {online
                                ? "Brain loaded"
                                : "API offline"}
                            </Pill>

                            <Pill>
                              {deviceLabel}
                            </Pill>

                            {cudaOn && (
                              <Pill tone="violet">
                                CUDA
                              </Pill>
                            )}

                            <Pill>
                              Local inference
                            </Pill>
                          </div>

                          {/* Suggestions */}
                          <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                            {SUGGESTIONS.map(
                              (suggestion) => (
                                <button
                                  key={
                                    suggestion
                                  }
                                  type="button"
                                  disabled={
                                    !online ||
                                    busy
                                  }
                                  onClick={() =>
                                    void send(
                                      suggestion,
                                    )
                                  }
                                  className="
                                    rounded-full
                                    border
                                    border-white/[0.06]
                                    bg-black/50
                                    px-2.5
                                    py-1.5
                                    text-[8px]
                                    text-zinc-600
                                    shadow-[0_3px_14px_rgba(0,0,0,0.14)]
                                    transition-all
                                    hover:border-violet-500/25
                                    hover:bg-violet-500/[0.055]
                                    hover:text-zinc-300
                                    disabled:opacity-30
                                  "
                                >
                                  {
                                    suggestion
                                  }
                                </button>
                              ),
                            )}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="mx-auto max-w-[620px] space-y-2.5 pb-3">
                        {msgs.map(
                          (message, index) => (
                            <div
                              key={index}
                              className={[
                                "flex",
                                message.role ===
                                "user"
                                  ? "justify-end"
                                  : "justify-start",
                              ].join(" ")}
                            >
                              <div
                                className={[
                                  "max-w-[82%]",
                                  "rounded-2xl",
                                  "px-3 py-2",
                                  "text-[11px] leading-relaxed",
                                  "shadow-[0_4px_18px_rgba(0,0,0,0.15)]",
                                  message.role ===
                                  "user"
                                    ? [
                                        "border",
                                        "border-violet-400/10",
                                        "bg-violet-600/25",
                                        "text-zinc-200",
                                      ].join(" ")
                                    : [
                                        "border",
                                        "border-white/[0.05]",
                                        "bg-[#09090a]/95",
                                        "text-zinc-400",
                                      ].join(" "),
                                  message.pending
                                    ? "opacity-50"
                                    : "",
                                ].join(" ")}
                              >
                                {message.text}
                              </div>
                            </div>
                          ),
                        )}

                        <div ref={bottom} />
                      </div>
                    )}
                  </div>
                </div>

                {/* Composer */}
                <div
                  className="
                    shrink-0
                    border-t
                    border-white/[0.045]
                    bg-[#000000]/95
                    px-4
                    py-2.5
                    backdrop-blur-xl
                  "
                >
                  <div className="mx-auto flex max-w-[620px] gap-1.5">
                    <input
                      ref={inputRef}
                      value={input}
                      onChange={(event) =>
                        setInput(
                          event.target.value,
                        )
                      }
                      onKeyDown={(event) => {
                        if (
                          event.key ===
                            "Enter" &&
                          !event.shiftKey
                        ) {
                          event.preventDefault();
                          void send();
                        }
                      }}
                      placeholder={
                        online
                          ? "Message DOOF…"
                          : "Start the DOOF API…"
                      }
                      disabled={
                        !online || busy
                      }
                      className="
                        min-w-0
                        flex-1
                        rounded-2xl
                        border
                        border-white/[0.06]
                        bg-[#080809]
                        px-3
                        py-2.5
                        text-[11px]
                        text-zinc-200
                        outline-none
                        shadow-[0_5px_24px_rgba(0,0,0,0.2)]
                        transition
                        placeholder:text-zinc-800
                        focus:border-violet-500/25
                        focus:shadow-[0_0_0_3px_rgba(139,92,246,0.045),0_5px_24px_rgba(0,0,0,0.2)]
                        disabled:opacity-40
                      "
                    />

                    <button
                      type="button"
                      onClick={() =>
                        void send()
                      }
                      disabled={
                        !online ||
                        busy ||
                        !input.trim()
                      }
                      className="
                        rounded-2xl
                        border
                        border-violet-400/20
                        bg-violet-600/80
                        px-3.5
                        py-2.5
                        text-[9px]
                        font-medium
                        text-white
                        shadow-[0_5px_20px_rgba(124,58,237,0.14)]
                        transition-all
                        hover:bg-violet-500
                        disabled:opacity-25
                      "
                    >
                      {busy
                        ? "…"
                        : "Send"}
                    </button>
                  </div>

                  <div className="mt-1 text-center text-[7px] uppercase tracking-[0.15em] text-zinc-900">
                    DOOF · local inference
                  </div>
                </div>
              </>
            )}

            {/* =================================================
                KNOWLEDGE
                ================================================= */}

            {page === "knowledge" && (
              <div className="flex min-h-0 flex-1 flex-col gap-2.5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[9px] text-zinc-700">
                    Training corpus · saved knowledge becomes{" "}
                    <code className="text-zinc-600">
                      data/train.txt
                    </code>
                  </p>

                  <div className="flex items-center gap-1.5">
                    <input
                      value={knowQuery}
                      onChange={(event) =>
                        setKnowQuery(
                          event.target.value,
                        )
                      }
                      placeholder="Search…"
                      className="
                        w-32
                        rounded-xl
                        border
                        border-white/[0.055]
                        bg-[#080809]
                        px-2.5
                        py-1.5
                        text-[9px]
                        text-zinc-300
                        outline-none
                        focus:border-violet-500/20
                      "
                    />

                    <Pill>
                      {filteredKnow.length} lines
                    </Pill>
                  </div>
                </div>

                <textarea
                  value={know}
                  onChange={(event) =>
                    setKnow(
                      event.target.value,
                    )
                  }
                  className="
                    min-h-0
                    flex-1
                    resize-none
                    rounded-2xl
                    border
                    border-white/[0.05]
                    bg-[#060607]
                    p-3
                    font-mono
                    text-[10px]
                    leading-relaxed
                    text-zinc-400
                    outline-none
                    shadow-[0_8px_30px_rgba(0,0,0,0.15)]
                    focus:border-violet-500/20
                  "
                  placeholder="One fact per line…"
                />

                <div>
                  <Btn
                    onClick={() =>
                      void saveKnow()
                    }
                  >
                    Save knowledge
                  </Btn>
                </div>
              </div>
            )}

            {/* =================================================
                TRAINING
                ================================================= */}

            {page === "training" && (
              <div className="flex-1 overflow-y-auto p-4">
                <div className="mb-3 flex flex-wrap items-center gap-1.5">
                  <Btn
                    onClick={() =>
                      void startTrain()
                    }
                    disabled={Boolean(
                      train.running,
                    )}
                  >
                    Start training
                  </Btn>

                  <Btn
                    variant="ghost"
                    onClick={() =>
                      void stopTrain()
                    }
                    disabled={
                      !train.running
                    }
                  >
                    Stop
                  </Btn>

                  <Pill
                    tone={
                      train.running
                        ? "violet"
                        : "neutral"
                    }
                  >
                    {String(
                      train.message ||
                        "idle",
                    )}
                  </Pill>

                  {train.loss != null && (
                    <Pill>
                      loss{" "}
                      {Number(
                        train.loss,
                      ).toFixed(4)}
                    </Pill>
                  )}

                  {!!train.step && (
                    <Pill>
                      step{" "}
                      {String(
                        train.step,
                      )}
                    </Pill>
                  )}
                </div>

                <div className="mb-3 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric
                    label="Device"
                    value={deviceLabel}
                  />

                  <Metric
                    label="CUDA"
                    value={
                      cudaOn
                        ? "available"
                        : "no"
                    }
                  />

                  <Metric
                    label="Epoch"
                    value={String(
                      train.epoch ??
                        "—",
                    )}
                  />

                  <Metric
                    label="LR"
                    value={String(
                      train.lr ??
                        "3e-4",
                    )}
                  />
                </div>

                <Panel className="p-3.5">
                  <div className="mb-2.5 text-[8px] uppercase tracking-[0.15em] text-zinc-700">
                    Loss curve
                  </div>

                  {history.length ===
                  0 ? (
                    <div className="py-10 text-center text-[10px] text-zinc-800">
                      No training history yet.
                    </div>
                  ) : (
                    <svg
                      viewBox="0 0 400 120"
                      className="h-28 w-full"
                    >
                      <polyline
                        fill="none"
                        stroke="rgb(139 92 246)"
                        strokeOpacity="0.7"
                        strokeWidth="1.5"
                        points={history
                          .map(
                            (
                              item,
                              index,
                            ) => {
                              const losses =
                                history.map(
                                  (
                                    entry,
                                  ) =>
                                    Number(
                                      entry.loss,
                                    ) ||
                                    0,
                                );

                              const min =
                                Math.min(
                                  ...losses,
                                );

                              const max =
                                Math.max(
                                  ...losses,
                                );

                              const x =
                                (index /
                                  Math.max(
                                    history.length -
                                      1,
                                    1,
                                  )) *
                                  380 +
                                10;

                              const y =
                                105 -
                                ((Number(
                                  item.loss,
                                ) -
                                  min) /
                                  Math.max(
                                    max -
                                      min,
                                    0.01,
                                  )) *
                                  85;

                              return `${x},${y}`;
                            },
                          )
                          .join(" ")}
                      />
                    </svg>
                  )}
                </Panel>
              </div>
            )}

            {/* =================================================
                MODELS
                ================================================= */}

            {page === "models" && (
              <div className="flex-1 overflow-y-auto p-4">
                <div className="mb-3 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric
                    label="Parameters"
                    value={String(
                      model.parameters ??
                        "—",
                    )}
                  />

                  <Metric
                    label="Device"
                    value={String(
                      model.device ??
                        "—",
                    )}
                  />

                  <Metric
                    label="d_model"
                    value={String(
                      model.d_model ??
                        "—",
                    )}
                  />

                  <Metric
                    label="Checkpoint"
                    value={ckptName}
                  />
                </div>

                <div className="mb-2 text-[8px] uppercase tracking-[0.15em] text-zinc-700">
                  Checkpoints
                </div>

                <div className="space-y-1.5">
                  {ckpts.length === 0 && (
                    <div
                      className="
                        rounded-xl
                        border border-white/[0.045]
                        bg-white/[0.01]
                        px-3
                        py-8
                        text-center
                        text-[10px]
                        text-zinc-800
                      "
                    >
                      No checkpoints found.
                    </div>
                  )}

                  {ckpts.map(
                    (checkpoint) => (
                      <div
                        key={String(
                          checkpoint.name,
                        )}
                        className="
                          flex
                          items-center
                          justify-between
                          gap-3
                          rounded-xl
                          border
                          border-white/[0.045]
                          bg-white/[0.012]
                          px-3
                          py-2
                          shadow-[0_4px_18px_rgba(0,0,0,0.12)]
                        "
                      >
                        <div className="min-w-0">
                          <div className="truncate text-[10px] text-zinc-300">
                            {String(
                              checkpoint.name,
                            )}
                          </div>

                          <div className="text-[8px] text-zinc-700">
                            {checkpoint.loss !=
                            null
                              ? `loss ${Number(checkpoint.loss).toFixed(3)}`
                              : ""}

                            {checkpoint.size_mb !=
                            null
                              ? ` · ${Number(checkpoint.size_mb).toFixed(1)} MB`
                              : ""}

                            {checkpoint.step !=
                            null
                              ? ` · step ${checkpoint.step}`
                              : ""}
                          </div>
                        </div>

                        <Btn
                          variant="ghost"
                          onClick={() =>
                            void loadCkpt(
                              String(
                                checkpoint.path ||
                                  checkpoint.name,
                              ),
                            )
                          }
                        >
                          Load
                        </Btn>
                      </div>
                    ),
                  )}
                </div>
              </div>
            )}

            {/* =================================================
                HARDWARE
                ================================================= */}

            {page === "hardware" && (
              <div className="flex-1 overflow-y-auto p-4">
                <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
                  {(
                    [
                      [
                        "Device",
                        String(
                          hw.device ??
                            "—",
                        ),
                      ],
                      [
                        "CUDA",
                        hw.cuda_available
                          ? "yes"
                          : "no",
                      ],
                      [
                        "MPS",
                        hw.mps_available
                          ? "yes"
                          : "no",
                      ],
                      [
                        "Torch",
                        String(
                          hw.torch_version ??
                            "—",
                        ),
                      ],
                      [
                        "Platform",
                        String(
                          hw.platform ??
                            "—",
                        ),
                      ],
                      [
                        "Python",
                        String(
                          hw.python ??
                            "—",
                        ),
                      ],
                      [
                        "CPUs",
                        String(
                          hw.cpu_count ??
                            "—",
                        ),
                      ],
                      [
                        "Machine",
                        String(
                          hw.machine ??
                            "—",
                        ),
                      ],
                    ] as [string, string][]
                  ).map(
                    ([label, value]) => (
                      <Metric
                        key={label}
                        label={label}
                        value={value}
                      />
                    ),
                  )}
                </div>
              </div>
            )}

            {/* =================================================
                SETTINGS
                ================================================= */}

            {page === "settings" && (
              <div className="flex-1 overflow-y-auto p-4">
                <div className="mx-auto max-w-lg space-y-5">
                  <section>
                    <div className="mb-2.5 text-[8px] uppercase tracking-[0.16em] text-zinc-700">
                      Inference
                    </div>

                    <Panel className="space-y-4 p-3.5">
                      {(
                        [
                          [
                            "temperature",
                            0.1,
                            2,
                            0.1,
                          ],
                          [
                            "max_new_tokens",
                            16,
                            256,
                            8,
                          ],
                          [
                            "top_k",
                            1,
                            100,
                            1,
                          ],
                        ] as const
                      ).map(
                        ([
                          key,
                          min,
                          max,
                          step,
                        ]) => (
                          <label
                            key={key}
                            className="block"
                          >
                            <div className="mb-1.5 flex justify-between text-[9px]">
                              <span className="text-zinc-600">
                                {key.replace(
                                  /_/g,
                                  " ",
                                )}
                              </span>

                              <span className="tabular-nums text-zinc-400">
                                {
                                  sett[
                                    key as keyof typeof sett
                                  ]
                                }
                              </span>
                            </div>

                            <input
                              type="range"
                              min={min}
                              max={max}
                              step={step}
                              value={
                                sett[
                                  key as keyof typeof sett
                                ]
                              }
                              onChange={(
                                event,
                              ) =>
                                setSett(
                                  (
                                    current,
                                  ) => ({
                                    ...current,
                                    [key]:
                                      key ===
                                      "temperature"
                                        ? parseFloat(
                                            event
                                              .target
                                              .value,
                                          )
                                        : parseInt(
                                            event
                                              .target
                                              .value,
                                            10,
                                          ),
                                  }),
                                )
                              }
                              className="w-full accent-violet-500"
                            />
                          </label>
                        ),
                      )}

                      <Btn
                        onClick={() =>
                          void saveSett()
                        }
                      >
                        Save settings
                      </Btn>
                    </Panel>
                  </section>

                  <section>
                    <div className="mb-2.5 text-[8px] uppercase tracking-[0.16em] text-zinc-700">
                      Cloud
                    </div>

                    <Panel className="flex items-center gap-2 p-3.5">
                      <StatusDot
                        on={Boolean(
                          cloud.connected,
                        )}
                      />

                      <span className="text-[9px] text-zinc-600">
                        {String(
                          cloud.message ||
                            cloud.status ||
                            "Offline mode · local only",
                        )}
                      </span>
                    </Panel>
                  </section>

                  <section>
                    <div className="mb-2.5 text-[8px] uppercase tracking-[0.16em] text-zinc-700">
                      About
                    </div>

                    <Panel className="p-3.5 text-[9px] leading-relaxed text-zinc-700">
                      DOOF v0.1 · local decoder-only
                      transformer · offline-first
                      personal AI
                    </Panel>
                  </section>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}