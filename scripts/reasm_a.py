#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parts=[(ROOT/"data"/f"ia_{i}.txt").read_text() for i in range(3)]
(ROOT/"scripts"/"install_v02_a.py").write_text("".join(parts))
print("assembled install_v02_a.py")
