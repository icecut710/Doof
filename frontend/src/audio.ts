/**
 * DOOF ambient audio — singleton, zero React re-renders on the beat path.
 *
 * - Local /arabicrap.mp3 (bundled via public/ → Vite dist → PyInstaller)
 * - Fallback: Supabase public object (CORS-friendly)
 * - Starts only when start() is called (after auth)
 * - Subtle delay-based atmosphere (no destructive file edits)
 * - Analyser → CSS --doof-beat / --doof-glow via rAF (throttled)
 */

const LOCAL_SRC = "./arabicrap.mp3";
const REMOTE_SRC =
  "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/arabicrap.mp3";

const LS_MUTE = "doof_ambient_mute";
const LS_VOL = "doof_ambient_vol";

/** Master gain when unmuted — very quiet by design */
const DEFAULT_VOLUME = 0.055;
const MIN_VOL = 0;
const MAX_VOL = 0.18;

type Listener = (s: { muted: boolean; volume: number; playing: boolean }) => void;

class DoofAudio {
  private ctx: AudioContext | null = null;
  private el: HTMLAudioElement | null = null;
  private master: GainNode | null = null;
  private analyser: AnalyserNode | null = null;
  private data: Uint8Array | null = null;
  private raf = 0;
  private started = false;
  private wanted = false;
  private listeners = new Set<Listener>();
  private smoothed = 0;

  private muted = localStorage.getItem(LS_MUTE) === "1";
  private volume = clamp(
    parseFloat(localStorage.getItem(LS_VOL) ?? String(DEFAULT_VOLUME)),
    MIN_VOL,
    MAX_VOL,
  );

  /** Call after successful auth. Safe to call multiple times. */
  start(): void {
    this.wanted = true;
    void this.ensurePlaying();
  }

  /** Call on logout. Stops playback and suspends the context. */
  stop(): void {
    this.wanted = false;
    this.stopBeatLoop();
    if (this.el) {
      try {
        this.el.pause();
        this.el.currentTime = 0;
      } catch {
        /* ignore */
      }
    }
    if (this.ctx && this.ctx.state === "running") {
      void this.ctx.suspend().catch(() => {});
    }
    this.writeBeat(0, 0.04);
    this.emit();
  }

  toggleMute(): void {
    this.muted = !this.muted;
    localStorage.setItem(LS_MUTE, this.muted ? "1" : "0");
    this.applyGain();
    this.emit();
  }

  setMuted(m: boolean): void {
    this.muted = m;
    localStorage.setItem(LS_MUTE, m ? "1" : "0");
    this.applyGain();
    this.emit();
  }

  setVolume(v: number): void {
    this.volume = clamp(v, MIN_VOL, MAX_VOL);
    localStorage.setItem(LS_VOL, String(this.volume));
    if (this.volume > 0.001 && this.muted) {
      this.muted = false;
      localStorage.setItem(LS_MUTE, "0");
    }
    this.applyGain();
    this.emit();
  }

  isMuted(): boolean {
    return this.muted;
  }

  getVolume(): number {
    return this.volume;
  }

  isPlaying(): boolean {
    return Boolean(this.el && !this.el.paused && this.wanted);
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    fn({ muted: this.muted, volume: this.volume, playing: this.isPlaying() });
    return () => this.listeners.delete(fn);
  }

  private emit(): void {
    const snap = { muted: this.muted, volume: this.volume, playing: this.isPlaying() };
    this.listeners.forEach((fn) => {
      try {
        fn(snap);
      } catch {
        /* ignore */
      }
    });
  }

  private applyGain(): void {
    if (!this.master) return;
    const g = this.muted ? 0 : this.volume;
    try {
      this.master.gain.setTargetAtTime(g, this.ctx!.currentTime, 0.05);
    } catch {
      this.master.gain.value = g;
    }
  }

  private writeBeat(beat: number, glow: number): void {
    const root = document.documentElement;
    root.style.setProperty("--doof-beat", beat.toFixed(3));
    root.style.setProperty("--doof-glow", glow.toFixed(3));
  }

  private stopBeatLoop(): void {
    if (this.raf) {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
    }
  }

  private startBeatLoop(): void {
    if (this.raf || !this.analyser || !this.data) return;
    const analyser = this.analyser;
    const data = this.data;
    let lastWrite = 0;

    const tick = (t: number) => {
      this.raf = requestAnimationFrame(tick);
      // ~30 Hz CSS updates — enough for subtle pulse, cheap
      if (t - lastWrite < 33) return;
      lastWrite = t;

      analyser.getByteFrequencyData(data as Uint8Array<ArrayBuffer>);
      // Low-mid energy (kick/bass region) — indices 1..8 of fftSize/2 bins
      let sum = 0;
      const n = Math.min(8, data.length);
      for (let i = 1; i < n; i++) sum += data[i];
      const raw = sum / (n * 255);
      // Smooth + soft curve so it never looks like a club visualizer
      this.smoothed = this.smoothed * 0.82 + raw * 0.18;
      const beat = Math.min(1, this.smoothed * 1.6);
      const glow = 0.035 + beat * 0.09;
      this.writeBeat(beat, glow);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private async ensurePlaying(): Promise<void> {
    if (!this.wanted) return;
    try {
      await this.boot();
      if (!this.wanted || !this.el || !this.ctx) return;

      if (this.ctx.state === "suspended") {
        await this.ctx.resume().catch(() => {});
      }

      this.applyGain();
      if (this.el.paused) {
        await this.el.play().catch(() => {
          // Autoplay may still be blocked; user mute toggle / interaction will retry
        });
      }
      this.startBeatLoop();
      this.emit();
    } catch {
      // Never block the app if audio fails
      this.writeBeat(0, 0.04);
    }
  }

  private async boot(): Promise<void> {
    if (this.started && this.el && this.ctx) return;

    const AC =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;

    const ctx = new AC();
    const el = new Audio();
    el.loop = true;
    el.preload = "auto";
    el.crossOrigin = "anonymous";
    el.volume = 1; // gain node owns level

    // Prefer bundled asset; fall back to public Supabase object
    el.src = LOCAL_SRC;
    el.addEventListener(
      "error",
      () => {
        if (el.src.includes("supabase")) return;
        el.src = REMOTE_SRC;
        el.load();
      },
      { once: true },
    );

    const source = ctx.createMediaElementSource(el);
    const dry = ctx.createGain();
    const wet = ctx.createGain();
    const master = ctx.createGain();
    const analyser = ctx.createAnalyser();

    dry.gain.value = 0.78;
    wet.gain.value = 0.22; // subtle atmosphere, not wash
    master.gain.value = this.muted ? 0 : this.volume;

    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.78;
    this.data = new Uint8Array(analyser.frequencyBinCount);

    // Lightweight dual-delay atmosphere (no convolver IR cost)
    const delay1 = ctx.createDelay(1.0);
    const delay2 = ctx.createDelay(1.0);
    delay1.delayTime.value = 0.09;
    delay2.delayTime.value = 0.21;
    const fb1 = ctx.createGain();
    const fb2 = ctx.createGain();
    fb1.gain.value = 0.22;
    fb2.gain.value = 0.14;
    const damp = ctx.createBiquadFilter();
    damp.type = "lowpass";
    damp.frequency.value = 2800;
    damp.Q.value = 0.5;

    source.connect(dry);
    source.connect(damp);
    damp.connect(delay1);
    delay1.connect(fb1);
    fb1.connect(delay1);
    delay1.connect(wet);
    damp.connect(delay2);
    delay2.connect(fb2);
    fb2.connect(delay2);
    delay2.connect(wet);

    dry.connect(master);
    wet.connect(master);
    master.connect(analyser);
    analyser.connect(ctx.destination);

    this.ctx = ctx;
    this.el = el;
    this.master = master;
    this.analyser = analyser;
    this.started = true;

    // If the element ends somehow, keep looping
    el.addEventListener("ended", () => {
      if (this.wanted) {
        el.currentTime = 0;
        void el.play().catch(() => {});
      }
    });
  }
}

function clamp(n: number, lo: number, hi: number): number {
  if (Number.isNaN(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
}

/** Singleton — one context, one element, one analyser for the whole app. */
export const doofAudio = new DoofAudio();
