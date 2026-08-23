"""DOOF local HTTP API."""
from __future__ import annotations
import json, platform, threading, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CKPT_DIR = ROOT / "checkpoints"
TRAIN = ROOT / "data" / "train.txt"
KNOW = ROOT / "data" / "knowledge.json"
SETT = ROOT / "data" / "settings.json"
_lock = threading.Lock()
_inf = None
_loaded = None
_train = {"running": False, "step": 0, "loss": None, "epoch": 0, "message": "idle", "history": [], "lr": 3e-4}
_stop = threading.Event()
_settings = {"temperature": 0.7, "max_new_tokens": 80, "top_k": 50, "context_length": 64}

def _cors(h):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")

def _json(h, code, data):
    b = json.dumps(data).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(b)))
    _cors(h)
    h.end_headers()
    h.wfile.write(b)

def _body(h):
    n = int(h.headers.get("Content-Length", 0))
    if n <= 0: return {}
    try: return json.loads(h.rfile.read(n))
    except Exception: return {}

def _find_ckpt(pref=None):
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    if pref:
        p = Path(pref) if Path(pref).is_absolute() else ROOT / pref
        if p.exists(): return p
    for n in ("doof_v01.pt", "doof_v0.1.pt"):
        if (CKPT_DIR / n).exists(): return CKPT_DIR / n
    steps = sorted(CKPT_DIR.glob("doof_step_*.pt"))
    if steps: return steps[-1]
    raise FileNotFoundError("No checkpoint. Run: python -m doof train")

def get_inf(ckpt=None):
    global _inf, _loaded
    with _lock:
        path = str(_find_ckpt(ckpt))
        if _inf is not None and _loaded == path: return _inf
        from doof.inference import DOOFInference
        _inf = DOOFInference(path)
        _loaded = path
        return _inf

def hardware():
    info = {"platform": platform.system(), "python": platform.python_version(), "machine": platform.machine(),
            "cuda_available": False, "cuda_device_count": 0, "cuda_devices": [], "cuda_version": None,
            "mps_available": False, "device": "cpu", "torch_version": None, "cpu_count": None}
    try:
        import os; info["cpu_count"] = os.cpu_count()
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["device"] = "cuda"; info["cuda_device_count"] = torch.cuda.device_count()
            info["cuda_version"] = getattr(torch.version, "cuda", None)
            for i in range(info["cuda_device_count"]):
                p = torch.cuda.get_device_properties(i)
                info["cuda_devices"].append({"index": i, "name": p.name, "total_memory_gb": round(p.total_memory/(1024**3), 2)})
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["mps_available"] = True; info["device"] = "mps"
    except Exception as e: info["error"] = str(e)
    return info

def model_info():
    try:
        inf = get_inf(); n = sum(p.numel() for p in inf.model.parameters())
        return {"loaded": True, "step": getattr(inf,"step",0), "loss": getattr(inf,"loss",None), "parameters": n,
                "parameters_m": round(n/1e6,2), "d_model": inf.model.d_model, "max_seq_len": inf.model.max_seq_len,
                "vocab_size": inf.tokenizer.vocab_size, "device": str(inf.device), "checkpoint": _loaded,
                "architecture": "decoder-only Transformer"}
    except Exception as e: return {"loaded": False, "error": str(e)}

def list_ckpts():
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(CKPT_DIR.glob("*.pt")):
        m = {"name": p.name, "path": str(p), "size_mb": round(p.stat().st_size/(1024*1024),2), "mtime": p.stat().st_mtime, "loaded": _loaded==str(p)}
        try:
            import torch
            ck = torch.load(p, map_location="cpu", weights_only=False)
            m["step"]=ck.get("step"); m["loss"]=ck.get("loss")
            mc=ck.get("model_config") or {}; m["d_model"]=mc.get("d_model"); m["max_seq_len"]=mc.get("max_seq_len")
        except Exception: pass
        out.append(m)
    return out

def knowledge_items():
    if KNOW.exists():
        try: return json.loads(KNOW.read_text())
        except Exception: pass
    items = []
    if TRAIN.exists():
        for i, line in enumerate(TRAIN.read_text().splitlines()):
            if line.strip(): items.append({"id": f"k-{i}", "text": line.strip(), "approved": True, "source": "train.txt"})
    return items

def save_knowledge(items):
    KNOW.parent.mkdir(parents=True, exist_ok=True)
    KNOW.write_text(json.dumps(items, indent=2))
    lines = [it["text"] for it in items if it.get("approved") and it.get("text")]
    TRAIN.write_text("\n".join(lines)+("\n" if lines else ""))

def run_train(epochs=3, resume_from=None):
    global _train, _inf, _loaded
    _stop.clear()
    try:
        import torch, torch.nn.functional as F
        from torch.amp import autocast
        from tqdm import tqdm
        from doof.training import DOOFTrainer, TrainingConfig
        cfg = TrainingConfig(data_path=str(TRAIN), checkpoint_dir=str(CKPT_DIR), epochs=epochs, batch_size=8, seq_len=64, learning_rate=3e-4, save_every=50)
        tr = DOOFTrainer(cfg)
        if resume_from:
            path = Path(resume_from) if Path(resume_from).is_absolute() else ROOT / resume_from
            if path.exists():
                ck = torch.load(path, map_location=tr.device, weights_only=False)
                tr.model.load_state_dict(ck["model_state_dict"])
        tokens = tr.load_data(); step=0; loss_val=0.0
        with _lock: _train.update({"running": True, "message": "training", "history": []})
        for epoch in range(cfg.epochs):
            if _stop.is_set(): break
            for _ in tqdm(range(100), desc=f"Epoch {epoch+1}"):
                if _stop.is_set(): break
                tr.model.train(); x,y = tr.create_batches(tokens)
                tr.optimizer.zero_grad(set_to_none=True)
                with autocast(device_type=tr.device.type, dtype=torch.float16, enabled=tr.device.type=="cuda"):
                    logits = tr.model(x); loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
                tr.scaler.scale(loss).backward(); tr.scaler.unscale_(tr.optimizer)
                torch.nn.utils.clip_grad_norm_(tr.model.parameters(), 1.0)
                tr.scaler.step(tr.optimizer); tr.scaler.update()
                step += 1; loss_val = float(loss.item())
                with _lock:
                    _train.update({"step": step, "loss": loss_val, "epoch": epoch+1, "message": f"step {step}"})
                    h=_train["history"]; h.append({"step": step, "loss": loss_val})
                    if len(h)>500: _train["history"]=h[-500:]
                if step % cfg.save_every == 0: tr.save_checkpoint(step, loss_val)
        tr.save_checkpoint(step, loss_val)
        torch.save({"model_state_dict": tr.model.state_dict(), "step": step, "loss": loss_val,
            "model_config": {"vocab_size": tr.tokenizer.vocab_size, "max_seq_len": cfg.seq_len, "d_model": tr.model.d_model}}, CKPT_DIR/"doof_v01.pt")
        with _lock: _inf=None; _loaded=None; _train.update({"running": False, "message": "complete", "step": step})
    except Exception as e:
        with _lock: _train.update({"running": False, "message": f"error: {e}", "error": traceback.format_exc()})

class Handler(BaseHTTPRequestHandler):
    def log_message(self, f, *a): print(f"[api] {a[0]}")
    def do_OPTIONS(self): self.send_response(204); _cors(self); self.end_headers()
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/","/api/health"): _json(self,200,{"ok":True,"service":"doof","version":"0.1.0"})
            elif path=="/api/hardware": _json(self,200,hardware())
            elif path=="/api/model": _json(self,200,model_info())
            elif path=="/api/checkpoints": _json(self,200,{"checkpoints": list_ckpts()})
            elif path=="/api/training":
                with _lock: _json(self,200,dict(_train))
            elif path=="/api/knowledge":
                items=knowledge_items(); _json(self,200,{"items":items,"text":"\n".join(i["text"] for i in items if i.get("approved"))})
            elif path=="/api/settings":
                with _lock: _json(self,200,dict(_settings))
            elif path=="/api/cloud":
                from doof.cloud import cloud_status; _json(self,200,cloud_status())
            else: _json(self,404,{"error":"not found"})
        except Exception as e: _json(self,500,{"error":str(e)})
    def do_POST(self):
        path=urlparse(self.path).path; body=_body(self)
        try:
            if path=="/api/generate":
                prompt=(body.get("prompt") or "").strip()
                if not prompt: _json(self,400,{"error":"prompt required"}); return
                with _lock: temp=float(body.get("temperature",_settings["temperature"])); mx=int(body.get("max_new_tokens",_settings["max_new_tokens"])); tk=int(body.get("top_k",_settings.get("top_k",50)))
                inf=get_inf(); t0=time.time(); text=inf.generate(prompt,max_new_tokens=mx,temperature=temp,top_k=tk)
                if text.startswith(prompt): text=text[len(prompt):].lstrip()
                _json(self,200,{"text":text,"prompt":prompt,"elapsed_ms":int((time.time()-t0)*1000)})
            elif path=="/api/training/start":
                with _lock:
                    if _train["running"]: _json(self,409,{"error":"already running"}); return
                    _train["running"]=True; _train["message"]="starting"
                threading.Thread(target=run_train,kwargs={"epochs":int(body.get("epochs",3)),"resume_from":body.get("resume_from")},daemon=True).start()
                _json(self,200,{"ok":True})
            elif path=="/api/training/stop": _stop.set(); _json(self,200,{"ok":True})
            elif path=="/api/knowledge":
                if "items" in body: save_knowledge(body["items"]); _json(self,200,{"ok":True,"count":len(body["items"])})
                elif "text" in body:
                    lines=[l.strip() for l in body["text"].splitlines() if l.strip()]
                    items=[{"id":f"k-{i}","text":l,"approved":True,"source":"edit"} for i,l in enumerate(lines)]
                    save_knowledge(items); _json(self,200,{"ok":True,"count":len(items)})
                else: _json(self,400,{"error":"items or text required"})
            elif path=="/api/settings":
                with _lock:
                    for k in ("temperature","max_new_tokens","top_k","context_length"):
                        if k in body: _settings[k]=float(body[k]) if k=="temperature" else int(body[k])
                    SETT.parent.mkdir(parents=True, exist_ok=True); SETT.write_text(json.dumps(_settings,indent=2))
                    _json(self,200,dict(_settings))
            elif path=="/api/model/load":
                global _inf, _loaded
                with _lock: _inf=None; _loaded=None
                try: get_inf(body.get("checkpoint") or body.get("path")); _json(self,200,{"ok":True,"checkpoint":_loaded})
                except Exception as e: _json(self,400,{"error":str(e)})
            elif path=="/api/reload":
                with _lock: _inf=None; _loaded=None
                _json(self,200,{"ok":True})
            else: _json(self,404,{"error":"not found"})
        except Exception as e: _json(self,500,{"error":str(e),"trace":traceback.format_exc()})

def run_server(host="127.0.0.1", port=8765):
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    if SETT.exists():
        try: _settings.update(json.loads(SETT.read_text()))
        except Exception: pass
    s = ThreadingHTTPServer((host, port), Handler)
    print(f"DOOF API listening on http://{host}:{port}")
    try: s.serve_forever()
    except KeyboardInterrupt: print("\nstopped"); s.shutdown()

if __name__ == "__main__":
    run_server()
