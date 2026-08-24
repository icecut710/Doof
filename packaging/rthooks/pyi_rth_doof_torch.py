# PyInstaller runtime hook — runs before any application import.
# Frozen CPU builds exclude torch.distributed to keep the zip small.
# Torch (and some crash dialogs) then report:
#   ModuleNotFoundError: No module named torchdistribute
# Install stubs so chat cannot die on that import.

import sys
import types


def _stub(name: str) -> None:
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    mod.is_available = lambda: False  # type: ignore[attr-defined]
    sys.modules[name] = mod


_stub("torchdistribute")
_stub("torch.distributed")
_stub("torch.distributed.algorithms")
_stub("torch.distributed.rpc")
_stub("torch.distributed.run")
