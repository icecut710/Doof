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
  };
  database?: {
    mode?: string;
    supabase_configured?: boolean;
    supabase_connected?: boolean;
    label?: string;
    detail?: string;
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
  };
  music?: { label?: string; detail?: string };
  auth?: { provider?: string; google?: string; email_verification?: boolean };
  problems?: { title: string; body: string; technical?: string | null; kind?: string }[];
};

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

function Card({
  title,
  label,
  detail,
  children,
}: {
  title: string;
  label?: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/90 p-4 shadow-[0_8px_30px_rgba(0,0,0,0.2)]">
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-500">{title}</div>
      {label && <div className="mt-1.5 text-[16px] font-semibold text-zinc-100">{label}</div>}
      {detail && <div className="mt-1 text-[13px] leading-relaxed text-zinc-500">{detail}</div>}
      {children}
    </section>
  );
}

export default function StatusTab({ online }: { online: boolean }) {
  const [data, setData] = useState<Status | null>(null);
  const [openTech, setOpenTech] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await getStatus(serverBase()));
    } catch {
      /* keep last */
    }
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

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center text-[13px] text-zinc-500">
        Checking the grill…
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">Is DOOF okay?</div>
        <div className="mt-1 flex flex-wrap items-end gap-3">
          <h1 className="text-[22px] font-semibold tracking-tight text-zinc-50">
            {data.health?.label || voice("healthy").label}
          </h1>
          <Pill on={online && data.health?.kind !== "offline"}>
            {data.mode === "connected" ? "Connected" : data.mode === "local" ? "Local only" : data.mode || "Unknown"}
          </Pill>
        </div>
        <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-zinc-500">
          {data.health?.detail}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Card title="Brain" label={data.brain?.label} detail={data.brain?.detail}>
          <div className="mt-3 flex flex-wrap gap-1.5 text-[12px] text-zinc-400">
            <Pill on={Boolean(data.brain?.torch_available)}>
              {data.brain?.torch_available ? "Local model" : "Backup brain"}
            </Pill>
            <span className="rounded-full border border-white/[0.06] px-2 py-0.5">
              {data.brain?.device || "cpu"}
            </span>
            {data.brain?.low_end && (
              <span className="rounded-full border border-amber-400/20 px-2 py-0.5 text-amber-300">
                Low-end mode
              </span>
            )}
          </div>
        </Card>

        <Card title="Database" label={data.database?.label} detail={data.database?.detail}>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Pill on>Local memory</Pill>
            <Pill on={Boolean(data.database?.supabase_connected)}>
              {data.database?.supabase_configured
                ? data.database?.supabase_connected
                  ? "Supabase connected"
                  : "Supabase configured, unreachable"
                : "Supabase not configured"}
            </Pill>
          </div>
        </Card>
      </div>

      <div className="mt-3">
        <Card
          title="Compute pool"
          label={`${data.network?.accepting ?? 0} grill${(data.network?.accepting ?? 0) === 1 ? "" : "s"} taking orders`}
          detail={data.network?.detail}
        >
          <p className="mt-2 text-[12px] leading-relaxed text-zinc-600">{data.network?.honest}</p>
          <div className="mt-3 space-y-2">
            {nodes.map((n) => (
              <div
                key={n.id || n.name}
                className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-white/[0.05] bg-black/30 px-3 py-2.5"
              >
                <div className="min-w-0">
                  <div className="text-[14px] font-medium text-zinc-100">
                    {n.nickname || n.name}
                    {n.is_local ? " " : ""}
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
                      ? "Available for work"
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
                    <span className="text-[11px] text-zinc-600">Not accepting remote jobs</span>
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
        </Card>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Card
          title="This machine"
          label={contribute.accepting_jobs ? voice("contribute_on").label : voice("contribute_off").label}
          detail={contribute.accepting_jobs ? voice("contribute_on").detail : voice("contribute_off").detail}
        >
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
        </Card>

        <Card title="Hardware" label={data.hardware?.cuda_available ? "Grill: Hot" : "Street cart energy"} detail={data.hardware?.cuda_available ? "A GPU is available for heavier jobs." : "CPU only — still a real grill, just slower."}>
          <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
            <div className="rounded-lg border border-white/[0.05] px-2.5 py-2">
              <div className="text-[11px] text-zinc-500">Device</div>
              <div className="text-zinc-200">{data.hardware?.device || "cpu"}</div>
            </div>
            <div className="rounded-lg border border-white/[0.05] px-2.5 py-2">
              <div className="text-[11px] text-zinc-500">CPU</div>
              <div className="text-zinc-200">{data.hardware?.cpu_count ?? "—"} cores</div>
            </div>
            <div className="rounded-lg border border-white/[0.05] px-2.5 py-2">
              <div className="text-[11px] text-zinc-500">RAM</div>
              <div className="text-zinc-200">{data.hardware?.ram_gb ? `${data.hardware.ram_gb} GB` : "—"}</div>
            </div>
            <div className="rounded-lg border border-white/[0.05] px-2.5 py-2">
              <div className="text-[11px] text-zinc-500">VRAM</div>
              <div className="text-zinc-200">
                {data.hardware?.cuda_devices?.[0]
                  ? `${data.hardware.cuda_devices[0].total_memory_gb} GB`
                  : "—"}
              </div>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Card title="Authentication" label={
          data.auth?.google === "available"
            ? "Google is at the door"
            : data.auth?.google === "temporarily_unavailable"
              ? "Google took a smoke break"
              : data.auth?.provider === "supabase"
                ? "Email is live"
                : "Local kitchen"
        } detail={
          data.auth?.google === "available"
            ? "Google sign-in is configured and available."
            : data.auth?.google === "temporarily_unavailable"
              ? "Google is configured but not answering right now."
              : data.auth?.provider === "supabase"
                ? "Email verification is on. Google is not configured."
                : "Accounts live on this machine until Supabase is configured."
        } />
        <Card title="DOOF FM" label={data.music?.label} detail={data.music?.detail} />
      </div>

      <div className="mt-3">
        <Card title="Recent problems" label={data.problems?.length ? `${data.problems.length} to look at` : "Quiet kitchen"} detail={data.problems?.length ? "Human-readable only. Technical details stay folded." : "Nothing standing between you and a fresh shawarma."}>
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
        </Card>
      </div>
    </div>
  );
}
