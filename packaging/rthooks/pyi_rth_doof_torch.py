# PyInstaller runtime hook — runs before application imports.
#
# IMPORTANT: Do NOT install a fake ``torch.distributed`` here.
# Pre-seeding sys.modules["torch.distributed"] with a stub causes:
#   AttributeError: partially initialized module 'torch' has no attribute 'distributed'
# because torch.__init__ expects to own that submodule during its own import.
#
# We only stub the *misspelled* module name that appears when some crash
# paths strip dots ("torchdistribute"). Real torch.distributed must come
# from the packaged Torch install (see doof.spec — no longer excluded).

import sys
import types


def _stub_misspelled() -> None:
    name = "torchdistribute"
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    mod.is_available = lambda: False  # type: ignore[attr-defined]
    sys.modules[name] = mod


_stub_misspelled()
