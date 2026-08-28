import { useCallback, useEffect, useState, type ReactNode } from "react";
import { voice } from "./personality";

type Node = {
  id: string;
  name: string;
  nickname?: string;
  gpu?: string;
  vram_gb?: number;
  device?: string;
  status?: string;
  state?: string;
  is_local?: boolean;
  accepting_jobs?: boolean;
  job_count?: number;
  max_jobs?: number;
  cpu_count?: number;
  ram_gb?: number;
  capabilities?: Record<string, boolean>;
  stale?: boolean;
  reachable?: boolean;
};

type Status = {
  mode?: string;
  health?: { kind?: string; label?: string; detail?: string };
  brain?: {
    torch_available?: boolean;
    loaded?: boolean;
    provider?: string;
    device?: string;
    low_end?: boolean;
    label?: string;
    detail?: string;
    torch_error?: string | null;
    torch_version?: string | null;
    cuda_available?: boolean;
    parameters_m?: number;
    d_model?: number;
    vocab_size?: number;
    n_layers?: number;
    checkpoint_name?: string;
  };
  database?: {
    mode?: string;
    supabase_configured?: boolean;
    supabase_connected?: boolean;
    label?: string;
    detail?: string;
    supabase_error?: string;
    error?: string;
  };
  model?: {
    versions?: { checkpoint_name?: string; status?: string; label?: string; promoted_at?: string | null; eval_passed?: boolean | null }[];
    production_checkpoint?: string | null;
    production_label?: string | null;
  };
  network?: {
    nodes?: Node[];
    online?: number;
    accepting?: number;
    label?: string;
    detail?: string;
    honest?: string;
  };
  compute?: {
    contribute?: {
      accepting_jobs?: boolean;
      accept_cpu?: boolean;
      accept_gpu?: boolean;
      max_jobs?: number;
      idle_only?: boolean;
    };
    job_count?: number;
  };
  hardware?: {
    device?: string;
    cuda_available?: boolean;
    cpu_count?: number | null;
    ram_gb?: number | null;
    cuda_devices?: { name: string; total_memory_gb: number }[];
    low_end?: boolean;
    platform?: string;
    python?: string;
    torch_version?: string | null;
    torch_error?: string | null;
  };
  music?: { label?: string; detail?: string };
  auth?: { provider?: string; google?: string; email_verification?: boolean };
  problems?: { title: string; body: string; technical?: string | null; kind?: string }[];
};

type DeviceInfo = {
  preference?: string;
  active_device?: string;
  active_label?: string;
  options?: { id: string; label: string; detail?: string; available?: boolean }[];
};

type HostedBrain = {
  config?: { enabled?: boolean; url?: string | null };
  health?: { available?: boolean; state?: string; label?: string; ms?: number | null };
};

async function getHostedBrain(base: string): Promise<HostedBrain | null> {
  const token = localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token");
  const res = await fetch(`${base}/api/brain/hosted`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return null;
  return (await res.json()) as HostedBrain;
}

async function getStatus(base: string): Promise<Status> {
  const token = localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token");
  const res = await fetch(`${base}/api/status`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return (await res.json()) as Status;
}

async function postSettings(base: string, body: Record<string, unknown>) {
  const token = localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token");
  await fetch(`${base}/api/compute/settings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
}

function serverBase() {
  try {
    return localStorage.getItem("doof_server") || "";
  } catch {
    return "";
  }
}

async function getDevice(base: string): Promise<DeviceInfo> {
  const token = localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token");
  const res = await fetch(`${base}/api/device`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return (await res.json()) as DeviceInfo;
}

async function postDevice(base: string, preference: string) {
  const token = localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token");
  await fetch(`${base}/api/device`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ preference }),
  });
}

function Pill({
  on,
  children,
}: {
  on?: boolean;
  children: string;
}) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[12px]",
        on
          ? "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300"
          : "border-white/[0.08] bg-white/[0.03] text-zinc-500",
      ].join(" ")}
    >
      <span className={["h-1.5 w-1.5 rounded-full", on ? "bg-emerald-400" : "bg-zinc-600"].join(" ")} />
      {children}
    </span>
  );
}

function StatusDot({ color }: { color: "green" | "amber" | "red" | "violet" | "zinc" }) {
  const colors = {
    green: "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]",
    amber: "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]",
    red: "bg-rose-400 shadow-[0_0_6px_rgba(251,113,133,0.5)]",
    violet: "bg-violet-400 shadow-[0_0_6px_rgba(167,139,250,0.5)]",
    zinc: "bg-zinc-600",
  };
  return <span className={`h-2 w-2 rounded-full ${colors[color]}`} />;
}

function GlassCard({
  title,
  accent,
  children,
}: {
  title: string;
  accent?: boolean;
  children?: ReactNode;
}) {
  return (
    <section
      className={[
        "rounded-2xl border p-4 shadow-[0_8px_30px_rgba(0,0,0,0.2)]",
        accent
          ? "border-violet-400/15 bg-[#0a0a0c]/90 shadow-[0_8px_30px_rgba(0,0,0,0.2),0_0_40px_rgba(124,58,237,0.04)]"
          : "border-white/[0.06] bg-[#0a0a0c]/90",
      ].join(" ")}
    >
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-500">{title}</div>
      {children}
    </section>
  );
}

function HWField({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-white/[0.05] bg-black/40 px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</div>
      <div
        className={[
          "mt-1 text-[13px] font-medium",
          accent ? "text-violet-300" : "text-zinc-200",
        ].join(" ")}
      >
        {value}
      </div>
    </div>
  );
}

function formatParams(m?: number): string {
  if (m == null) return "—";
  if (m >= 1000) return `${(m / 1000).toFixed(1)}B`;
  return `${m}M`;
}

export default function StatusTab({ online }: { online: boolean }) {
  const [data, setData] = useState<Status | null>(null);
  const [device, setDevice] = useState<DeviceInfo | null>(null);
  const [hosted, setHosted] = useState<HostedBrain | null>(null);
  const [openTech, setOpenTech] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await getStatus(serverBase()));
    } catch {
      /* keep last */
    }
    try {
      setDevice(await getDevice(serverBase()));
    } catch {
      /* device info optional */
    }
    getHostedBrain(serverBase())
      .then((h) => setHosted(h))
      .catch(() => setHosted(null));
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), online ? 6000 : 15000);
    return () => clearInterval(t);
  }, [load, online]);

  const contribute = data?.compute?.contribute || {};
  const nodes = data?.network?.nodes || [];

  const toggle = async (key: string, value: boolean | number) => {
    setSaving(true);
    try {
      await postSettings(serverBase(), { ...contribute, [key]: value });
      await load();
    } finally {
      setSaving(false);
    }
  };

  const PRESETS: Record<string, Record<string, boolean | number>> = {
    light: {
      max_jobs: 1,
      idle_only: true,
      allow_train: false,
      allow_inference: true,
      allow_embedding: true,
      pause_on_battery: true,
    },
    balanced: {
      max_jobs: 1,
      idle_only: false,
      allow_train: false,
      allow_inference: true,
      allow_embedding: true,
      pause_on_battery: true,
    },
    performance: {
      max_jobs: 2,
      idle_only: false,
      allow_train: true,
      allow_inference: true,
      allow_embedding: true,
      pause_on_battery: false,
    },
    blunt: {
      max_jobs: 3,
      idle_only: false,
      allow_train: true,
      allow_inference: true,
      allow_embedding: true,
      pause_on_battery: false,
    },
  };

  const activePreset =
    Object.keys(PRESETS).find((k) => {
      const preset = PRESETS[k];
      return Object.entries(preset).every(([key, val]) => {
        const cur = (contribute as Record<string, unknown>)[key];
        return cur === undefined || cur === val;
      });
    }) || null;

  const applyPreset = async (key: string) => {
    setSaving(true);
    try {
      await postSettings(serverBase(), { ...contribute, ...PRESETS[key] });
      await load();
    } finally {
      setSaving(false);
    }
  };

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center text-[13px] text-zinc-500">
        Connecting to DOOF…
      </div>
    );
  }

  const hw = data.hardware;
  const br = data.brain;

  const gpuName = hw?.cuda_devices?.[0]?.name || hw?.device || "CPU";
  const cudaStatus = hw?.cuda_available
    ? "Available"
    : hw?.torch_error
      ? hw.torch_error.length > 40
        ? hw.torch_error.slice(0, 37) + "…"
        : hw.torch_error
      : "Unavailable";
  const platform = hw?.platform || "—";
  const pythonVer = hw?.python || "—";
  const torchVer = hw?.torch_version || "—";
  const cpuCores = hw?.cpu_count != null ? String(hw.cpu_count) : "—";
  const ram = hw?.ram_gb != null ? `${hw.ram_gb} GB` : "—";
  const vram = hw?.cuda_devices?.[0] ? `${hw.cuda_devices[0].total_memory_gb} GB` : "N/A";
  const inference = hw?.cuda_available ? "CUDA" : "CPU";
  const brainLabel = br?.checkpoint_name || "DOOF v3";
  const params = formatParams(br?.parameters_m);

  let hwStatus: "Ready" | "Loading" | "Offline" | "Error" = "Offline";
  if (br?.loaded) hwStatus = "Ready";
  else if (br?.torch_error) hwStatus = "Error";
  else if (br?.torch_available) hwStatus = "Loading";

  const overallOk = online && data.health?.kind !== "offline";

  const statusColor: "green" | "amber" | "red" | "zinc" =
    hwStatus === "Ready"
      ? "green"
      : hwStatus === "Loading"
        ? "amber"
        : hwStatus === "Error"
          ? "red"
          : "zinc";

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">System status</div>
        <div className="mt-1 flex flex-wrap items-end gap-3">
          <h1 className="text-[22px] font-semibold tracking-tight text-zinc-50">
            {data.health?.label || voice("healthy").label}
          </h1>
          <Pill on={overallOk}>
            {data.mode === "connected"
              ? "Connected"
              : data.mode === "local"
                ? "Local only"
                : data.mode || "Unknown"}
          </Pill>
        </div>
        <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-zinc-500">
          {data.health?.detail}
        </p>
      </div>

      <GlassCard title="Hardware" accent>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          <HWField label="Device" value={gpuName} />
          <HWField label="CUDA" value={cudaStatus} accent={hw?.cuda_available} />
          <HWField label="Platform" value={platform} />
                    <HWField label="Runtime" value={pythonVer} />
          <HWField label="Model engine" value={torchVer} />
          <HWField label="CPU" value={`${cpuCores} cores`} />
          <HWField label="RAM" value={ram} />
          <HWField label="VRAM" value={vram} />
          <HWField label="Inference" value={inference} accent={inference === "CUDA"} />
          <HWField label="Brain" value={brainLabel} />
          <HWField label="Parameters" value={params} />
          <div className="rounded-xl border border-white/[0.05] bg-black/40 px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Status</div>
            <div className="mt-1 flex items-center gap-2">
              <StatusDot color={statusColor} />
              <span className="text-[13px] font-medium text-zinc-200">{hwStatus}</span>
            </div>
          </div>
        </div>
        {hw?.torch_error && (
          <div className="mt-2 rounded-lg border border-rose-400/20 bg-rose-400/5 px-3 py-2 text-[11px] text-red-300">
            <span className="font-medium">Torch Error:</span> {hw.torch_error}
          </div>
        )}
        {device && (device.options?.length ?? 0) > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/[0.04] pt-3">
            <span className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">
              Inference device
            </span>
            <select
              value={device.preference || "auto"}
              disabled={saving}
              onChange={(e) => {
                const pref = e.target.value;
                setSaving(true);
                setDevice({ ...device, preference: pref });
                postDevice(serverBase(), pref)
                  .then(() => load())
                  .finally(() => setSaving(false));
              }}
              className="rounded-lg border border-white/[0.08] bg-black/50 px-2 py-1 text-[12px] text-zinc-200 outline-none focus:border-violet-400/40"
            >
              {(device.options || []).map((o) => (
                <option key={o.id} value={o.id} disabled={o.available === false}>
                  {o.label}
                  {o.available === false ? " (unavailable)" : ""}
                </option>
              ))}
            </select>
            {device.active_label && (
              <span className="text-[11px] text-zinc-600">Using {device.active_label}</span>
            )}
          </div>
        )}
      </GlassCard>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <GlassCard title="Brain">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">{br?.label}</div>
          {br?.detail && (
            <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">{br.detail}</div>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5 text-[12px] text-zinc-400">
            <Pill on={Boolean(br?.torch_available)}>
              {br?.torch_available ? "Local model" : "Remote only"}
            </Pill>
            <span className="rounded-full border border-white/[0.06] px-2 py-0.5">
              {br?.device || "cpu"}
            </span>
            {br?.torch_version && (
              <span className="rounded-full border border-white/[0.06] px-2 py-0.5">
                Torch {br.torch_version}
              </span>
            )}
            {br?.cuda_available && (
              <span className="rounded-full border border-green-400/20 px-2 py-0.5 text-green-300">
                CUDA
              </span>
            )}
                        {br?.low_end && (
              <span className="rounded-full border border-amber-400/20 px-2 py-0.5 text-amber-300">
                Low-end mode
              </span>
            )}
            {hosted?.config?.enabled && hosted.health && (
              <span
                className={[
                  "rounded-full border px-2 py-0.5",
                  hosted.health.available
                    ? "border-emerald-400/20 text-emerald-300"
                    : "border-amber-400/20 text-amber-300",
                ].join(" ")}
              >
                Hosted brain · {hosted.health.state || "unknown"}
                {hosted.health.ms != null ? ` · ${hosted.health.ms}ms` : ""}
              </span>
            )}
          </div>
          {br?.parameters_m != null && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="rounded-full border border-white/[0.06] px-2 py-0.5 text-[12px] text-zinc-400">
                {formatParams(br.parameters_m)} params
              </span>
            </div>
          )}
          {/* Collapsible technical details for the curious friend */}
          <details className="mt-3">
            <summary className="cursor-pointer text-[11px] text-zinc-600 underline-offset-2 hover:text-zinc-300 hover:underline">
              Technical details
            </summary>
            <div className="mt-2 space-y-1 text-[11px] text-zinc-600">
              {br?.torch_version && <div>Model engine: {br.torch_version}</div>}
              {br?.checkpoint_name && <div>Checkpoint: {br.checkpoint_name}</div>}
              {br?.d_model && <div>d_model: {br.d_model}</div>}
              {br?.vocab_size && <div>Vocabulary: {br.vocab_size}</div>}
              {br?.n_layers && <div>Layers: {br.n_layers}</div>}
            </div>
          </details>
        </GlassCard>

        <GlassCard title="Database">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">
            {data.database?.mode === "connected"
              ? "Cloud Sync"
              : data.database?.supabase_configured
                ? "Not connected"
                : "Local only"}
          </div>
          <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">
            {data.database?.mode === "connected"
              ? "Memory and training data sync across your devices."
              : data.database?.supabase_configured
                ? "Cloud Sync is configured but not currently connected."
                : "All data stays on this machine. Enable Cloud Sync in Settings to share across devices."}
          </div>
          {data.database?.supabase_error && (
            <div className="mt-2 rounded-lg border border-rose-400/20 bg-rose-400/[0.04] px-3 py-2 text-[11px] text-rose-300">
              {data.database.supabase_error}
            </div>
          )}
          {data.database?.error && !data.database.supabase_error && (
            <div className="mt-2 text-[11px] text-rose-300">{data.database.error}</div>
          )}
        </GlassCard>

        <GlassCard title="Network">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">{data.network?.label || "Local network"}</div>
          {data.network?.detail && (
            <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">{data.network.detail}</div>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Pill on>Local memory</Pill>
            <Pill on>Honest mode</Pill>
          </div>
        </GlassCard>
      </div>

      <div className="mt-3">
        <GlassCard title="Brain Network">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">
            {data.network?.accepting ?? 0} node{(data.network?.accepting ?? 0) === 1 ? "" : "s"} online
          </div>
          {data.network?.detail && (
            <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">{data.network.detail}</div>
          )}
          {data.network?.honest && (
            <p className="mt-2 text-[12px] leading-relaxed text-zinc-600">{data.network.honest}</p>
          )}
          <div className="mt-3 space-y-2">
            {nodes.map((n) => (
              <div
                key={n.id || n.name}
                className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-white/[0.05] bg-black/30 px-3 py-2.5"
              >
                <div className="min-w-0">
                  <div className="text-[14px] font-medium text-zinc-100">
                    {n.nickname || n.name}
                    {n.is_local ? " (this machine)" : ""}
                  </div>
                  <div className="mt-0.5 text-[12px] text-zinc-500">
                    {n.gpu || "CPU"}
                    {n.vram_gb ? ` · ${n.vram_gb} GB VRAM` : ""}
                    {n.ram_gb ? ` · ${n.ram_gb} GB RAM` : ""}
                    {` · jobs ${n.job_count ?? 0}/${n.max_jobs ?? 1}`}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Pill on={n.state === "available_for_work" || n.state === "connected"}>
                    {n.state === "available_for_work"
                      ? "Available"
                      : n.state === "connected"
                        ? "Connected"
                        : n.state === "reachable"
                          ? "Reachable"
                          : n.stale
                            ? "Resting"
                            : "Registered"}
                  </Pill>
                  {n.accepting_jobs ? (
                    <span className="text-[11px] text-violet-300">Contributing</span>
                  ) : (
                    <span className="text-[11px] text-zinc-600">Not accepting jobs</span>
                  )}
                </div>
              </div>
            ))}
            {nodes.length === 0 && (
              <div className="rounded-xl border border-dashed border-white/[0.06] px-3 py-6 text-center text-[13px] text-zinc-500">
                No nodes yet. This machine will appear after the first heartbeat.
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <GlassCard title="This machine">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">
            {contribute.accepting_jobs ? voice("contribute_on").label : voice("contribute_off").label}
          </div>
          <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">
            {contribute.accepting_jobs ? voice("contribute_on").detail : voice("contribute_off").detail}
          </div>
          <label className="mt-3 flex items-center justify-between gap-3 text-[13px] text-zinc-300">
            Contribute compute
            <button
              type="button"
              disabled={saving}
              onClick={() => void toggle("accepting_jobs", !contribute.accepting_jobs)}
              className={[
                "rounded-full border px-3 py-1 text-[12px] font-medium",
                contribute.accepting_jobs
                  ? "border-violet-400/30 bg-violet-500/20 text-violet-100"
                  : "border-white/[0.08] text-zinc-400",
              ].join(" ")}
            >
              {contribute.accepting_jobs ? "On" : "Off"}
            </button>
          </label>
          <div className="mt-2 space-y-1.5 text-[13px] text-zinc-400">
            <label className="flex items-center justify-between">
              Accept CPU jobs
              <input
                type="checkbox"
                checked={Boolean(contribute.accept_cpu)}
                onChange={(e) => void toggle("accept_cpu", e.target.checked)}
              />
            </label>
            <label className="flex items-center justify-between">
              Accept GPU jobs
              <input
                type="checkbox"
                checked={Boolean(contribute.accept_gpu)}
                onChange={(e) => void toggle("accept_gpu", e.target.checked)}
              />
            </label>
            <div className="mt-2 space-y-1.5 text-[13px] text-zinc-400">
            <div className="flex items-center justify-between">
              <span>Resource usage</span>
              <span className="text-[11px] text-zinc-600">presets below</span>
            </div>
            <div className="grid grid-cols-4 gap-1.5 pt-0.5">
              {[
                { key: "light", label: "Light", desc: "Only when idle. Keeps the PC cool and quiet." },
                { key: "balanced", label: "Balanced", desc: "One job at a time, pauses on battery." },
                { key: "performance", label: "Performance", desc: "More jobs, uses more of this PC." },
                { key: "blunt", label: "Hit Mom's Blunt", desc: "Maximum allowed intensity. CPU/GPU safety caps stay on — DOOF still won't cook your machine." },
              ].map((p) => (
                <button
                  key={p.key}
                  type="button"
                  disabled={saving}
                  title={p.desc}
                  onClick={() => void applyPreset(p.key)}
                  data-preset={p.key}
                  className={activePreset === p.key
                    ? p.key === "blunt"
                      ? "rounded-lg border border-fuchsia-400/40 bg-fuchsia-500/[0.16] px-2 py-1 text-[11px] text-fuchsia-200 shadow-[0_0_14px_rgba(232,121,249,0.18)]"
                      : "rounded-lg border border-violet-400/30 bg-violet-500/[0.12] px-2 py-1 text-[12px] text-violet-200"
                    : "rounded-lg border border-white/[0.07] bg-white/[0.02] px-2 py-1 text-[11px] text-zinc-400 hover:border-white/[0.14] hover:text-zinc-200"}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <p className="text-[11px] leading-relaxed text-zinc-600">
              Light works only while idle · Balanced allows one job at a time · Performance lifts limits.
              DOOF never maxes out your computer by default.
              {activePreset === "blunt" && (
                <span className="text-fuchsia-300/80"> Blunt mode runs up to 3 jobs at once — CPU is still capped at 80% and GPU at 90%, always.</span>
              )}
            </p>
          </div>
          <label className="flex items-center justify-between">
              Idle only
              <input
                type="checkbox"
                checked={Boolean(contribute.idle_only)}
                onChange={(e) => void toggle("idle_only", e.target.checked)}
              />
            </label>
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-zinc-600">
            Friends never silently use this PC. Jobs are typed (chat, embeddings, training) — never arbitrary code.
          </p>
        </GlassCard>

        <GlassCard title="Authentication">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">
            {data.auth?.provider === "cloud" ? "Email active" : "Local accounts"}
          </div>
          <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">
            {data.auth?.provider === "cloud"
              ? "Email verification is enabled."
              : "Accounts stay on this machine until Cloud Sync is configured."}
          </div>
        </GlassCard>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <GlassCard title="DOOF FM">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">{data.music?.label}</div>
          {data.music?.detail && (
            <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">{data.music.detail}</div>
          )}
        </GlassCard>

        <GlassCard title="Recent problems">
          <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">
            {data.problems?.length ? `${data.problems.length} to look at` : "All clear"}
          </div>
          <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">
            {data.problems?.length
              ? "Human-readable only. Technical details stay folded."
              : "Nothing standing between you and a fresh thought."}
          </div>
          <div className="mt-3 space-y-2">
            {(data.problems || []).map((p, i) => (
              <div key={i} className="rounded-xl border border-white/[0.05] px-3 py-2">
                <div className="text-[14px] text-zinc-100">{p.title}</div>
                <div className="mt-0.5 text-[13px] text-zinc-500">{p.body}</div>
                {p.technical && (
                  <button
                    type="button"
                    className="mt-1 text-[12px] text-zinc-600 underline-offset-2 hover:text-zinc-400 hover:underline"
                    onClick={() => setOpenTech(openTech === p.technical ? null : p.technical || null)}
                  >
                    {openTech === p.technical ? "Hide technical details" : "Technical details"}
                  </button>
                )}
                {openTech === p.technical && (
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded-lg bg-black/40 p-2 text-[11px] text-zinc-500">
                    {p.technical}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="mt-4 rounded-2xl border border-violet-400/10 bg-violet-500/[0.03] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-violet-300/80">🧠</span>
          <span className="text-[11px] uppercase tracking-[0.14em] text-violet-400/60">DOOF says</span>
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-zinc-500">
          {hw?.cuda_available
            ? "GPU is hot and ready. Feed me something heavy."
            : br?.loaded
              ? "Brain is loaded. CPU-only, but we make it work."
              : "Systems nominal. I only bite when the context window is full."}
        </p>
      </div>
    </div>
  );
}
