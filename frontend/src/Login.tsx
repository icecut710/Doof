import { useEffect, useState, type FormEvent } from "react";
import { getServer, setServer, storeToken, type Profile } from "./auth";

type AuthConfig = {
  provider: "local" | "supabase";
  oauth: boolean;
  email_verification: boolean;
  authorize_url?: string;
};

async function post(path: string, body: unknown): Promise<Record<string, unknown>> {
  const res = await fetch(`${getServer()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok)
    throw Object.assign(
      new Error((json as { error?: string }).error ?? "Request failed"),
      { code: (json as { code?: string }).code },
    );
  return json as Record<string, unknown>;
}

export default function Login({ onLogin }: { onLogin: (p: Profile) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [server, setServerUrl] = useState(getServer());
  const [showServer, setShowServer] = useState(false);
  const [remember, setRemember] = useState(true);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [checkEmail, setCheckEmail] = useState(false);

  // Auth capabilities — fetched once
  useEffect(() => {
    fetch(`${getServer()}/api/auth/config`)
      .then((r) => r.json())
      .then((c: AuthConfig) => setCfg(c))
      .catch(() =>
        setCfg({ provider: "local", oauth: false, email_verification: false }),
      );
  }, []);

  const finish = (data: { token: string; profile: Profile }) => {
    storeToken(data.token, remember);
    onLogin(data.profile);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      return setErr("Enter a valid email address.");
    if (password.length < 6)
      return setErr("Password must be at least 6 characters.");
    setBusy(true);
    try {
      setServer(server);
      const data = await post(
        mode === "login" ? "/api/auth/login" : "/api/auth/signup",
        { email, password },
      );
      if (data.status === "verify_email_sent") setCheckEmail(true);
      else finish(data as unknown as { token: string; profile: Profile });
    } catch (ex) {
      const e2 = ex as Error & { code?: string };
      if (e2.code === "email_unverified") setCheckEmail(true);
      else setErr(e2.message);
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setErr("");
    try {
      await post("/api/auth/resend", { email });
      setErr("Verification email resent.");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  };

  const google = () => {
    if (!cfg?.authorize_url) return;
    setServer(server);
    const redirect = `${window.location.origin}${window.location.pathname}`;
    window.location.href = `${cfg.authorize_url}&redirect_to=${encodeURIComponent(redirect)}`;
  };

  if (checkEmail) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="doof-fade w-full max-w-[340px] rounded-3xl border border-white/[0.06] bg-[#09090b]/92 p-6 text-center shadow-[0_20px_70px_rgba(0,0,0,0.5)] backdrop-blur-md">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-500/[0.06] text-[16px] text-cyan-300">
            ✉
          </div>
          <h1 className="mt-3 text-[15px] font-semibold tracking-tight text-zinc-100">
            CHECK YOUR EMAIL
          </h1>
          <p className="mt-1.5 text-[10px] leading-relaxed text-zinc-400">
            Verify your email before entering DOOF.
          </p>
          <p className="mt-0.5 truncate text-[9px] text-zinc-600">{email}</p>
          {err && <div className="mt-2 text-[9px] text-emerald-400/80">{err}</div>}
          <button
            type="button"
            onClick={() => void resend()}
            disabled={busy}
            className="mt-4 w-full rounded-xl border border-violet-400/20 bg-violet-600/70 py-2 text-[10px] font-medium text-white transition hover:bg-violet-500 disabled:opacity-40"
          >
            Resend verification email
          </button>
          <button
            type="button"
            onClick={() => {
              setCheckEmail(false);
              setMode("login");
              setErr("");
            }}
            className="mt-2 w-full rounded-xl border border-white/[0.06] py-2 text-[10px] text-zinc-400 transition hover:bg-white/[0.03]"
          >
            Back to sign in
          </button>
        </div>
      </div>
    );
  }

  const input =
    "w-full rounded-xl border border-white/[0.07] bg-black/60 px-3 py-2 text-[12px] text-zinc-200 outline-none transition placeholder:text-zinc-600 focus:border-violet-400/30 focus:bg-violet-500/[0.03]";
  const btn =
    "w-full rounded-xl border border-violet-400/20 bg-violet-600/80 py-2 text-[11px] font-medium text-white transition hover:bg-violet-500 disabled:opacity-40";

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="doof-fade w-full max-w-[340px]">
        <div className="rounded-3xl border border-white/[0.06] bg-[#09090b]/92 p-6 shadow-[0_20px_70px_rgba(0,0,0,0.5),0_0_50px_rgba(124,58,237,0.06)] backdrop-blur-md">
          {/* Logo */}
          <div className="mb-5 text-center">
            <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/[0.07] text-[16px] font-bold text-violet-300 shadow-[0_0_30px_rgba(124,58,237,0.18)]">
              ◆
            </div>
            <h1 className="mt-3 text-[18px] font-semibold tracking-tight text-zinc-100">DOOF</h1>
            <p className="mt-0.5 text-[9px] uppercase tracking-[0.22em] text-zinc-600">
              Private intelligence OS
            </p>
          </div>

          <form onSubmit={submit} className="space-y-2.5">
            <input
              className={input}
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
            />
            <div className="relative">
              <input
                className={input + " pr-10"}
                type={showPw ? "text" : "password"}
                required
                minLength={6}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                tabIndex={-1}
                onClick={() => setShowPw(!showPw)}
                title={showPw ? "Hide password" : "Show password"}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg px-1.5 py-1 text-[11px] text-zinc-500 transition hover:text-violet-300"
              >
                {showPw ? "🙈" : "👁"}
              </button>
            </div>

            {mode === "signup" && (
              <p className="px-1 text-[8px] leading-relaxed text-zinc-600">
                First account becomes <span className="text-violet-300">Owner</span>. Friends join
                as Trusted Users — one shared brain.
              </p>
            )}

            {showServer && (
              <input
                className={input}
                placeholder="Brain server URL (http://host:8765)"
                value={server}
                onChange={(e) => setServerUrl(e.target.value)}
              />
            )}

            {err && (
              <div
                className={
                  err.includes("resent")
                    ? "rounded-lg border border-emerald-500/15 bg-emerald-500/[0.05] px-3 py-1.5 text-[9px] text-emerald-300/90"
                    : "rounded-lg border border-rose-500/15 bg-rose-500/[0.06] px-3 py-1.5 text-[9px] text-rose-300/90"
                }
              >
                {err}
              </div>
            )}

            <label className="flex cursor-pointer items-center gap-1.5 px-1 pt-0.5 text-[9px] text-zinc-500">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="accent-violet-500"
              />
              Remember session
            </label>

            <button className={btn} type="submit" disabled={busy}>
              {busy ? "Connecting…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          {/* Real Google OAuth via Supabase — only shown when configured */}
          {cfg?.oauth && (
            <>
              <div className="my-3 flex items-center gap-2">
                <div className="h-px flex-1 bg-white/[0.06]" />
                <span className="text-[8px] uppercase tracking-widest text-zinc-700">or</span>
                <div className="h-px flex-1 bg-white/[0.06]" />
              </div>
              <button
                type="button"
                onClick={google}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white py-2 text-[11px] font-medium text-zinc-800 transition hover:bg-zinc-100"
              >
                <svg width="14" height="14" viewBox="0 0 48 48" aria-hidden>
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
                </svg>
                Continue with Google
              </button>
            </>
          )}

          <div className="mt-4 flex items-center justify-between border-t border-white/[0.04] pt-3">
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "signup" : "login");
                setErr("");
              }}
              className="text-[9px] text-zinc-500 transition hover:text-violet-300"
            >
              {mode === "login" ? "Create account" : "Have an account? Sign in"}
            </button>
            <button
              type="button"
              onClick={() => setShowServer(!showServer)}
              className="text-[9px] text-zinc-500 transition hover:text-violet-300"
            >
              Join existing brain
            </button>
          </div>
        </div>

        <p className="mt-3 text-center text-[8px] tracking-wide text-zinc-700">
          v0.2α · local-first · shared brain
        </p>
      </div>
    </div>
  );
}
