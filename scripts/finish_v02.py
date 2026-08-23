#!/usr/bin/env python3
from pathlib import Path
import base64, zlib, tarfile, io, subprocess
ROOT = Path(__file__).resolve().parents[1]
bundle = "".join((ROOT/"data"/f"rem_{i}.b64").read_text().strip() for i in range(8))
raw = zlib.decompress(base64.b64decode(bundle))
with tarfile.open(fileobj=io.BytesIO(raw), mode="r") as tar:
    tar.extractall(ROOT / "data")
print("ok chunks")
subprocess.check_call(["python3", str(ROOT/"scripts"/"apply_v02_api.py")])
subprocess.check_call(["python3", str(ROOT/"scripts"/"apply_v02_ui.py")])
print("DOOF v0.2 API+UI applied")
