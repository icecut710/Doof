"""DOOF v0.3 route/brain integration layer."""
from __future__ import annotations

_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    try:
        from doof import api as api_mod
        from doof.api_extra import try_handle
        from doof.brain import memory_answer, math_answer
    except Exception as exc:
        print(f"[api_mount] skip: {exc}")
        return

    def _memory_fallback(prompt, memories=None):
        math = math_answer(prompt or "")
        if math:
            return math
        mem = memory_answer(prompt or "", memories or [])
        if mem:
            return mem
        return "The model could not generate a response. Try rephrasing, or add relevant information to Memory so DOOF can help."

    api_mod._answer_from_memory = _memory_fallback

    try:
        from doof.compute.pool_patch import install as patch_pool
        patch_pool()
    except Exception as exc:
        print(f"[api_mount] pool_patch: {exc}")

    Handler = getattr(api_mod, "Handler", None)
    if Handler is None:
        return
    if getattr(Handler, "_doof_v03_wrapped", False):
        _installed = True
        return

    _orig_get = Handler.do_GET
    _orig_post = Handler.do_POST

    def do_GET(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        try:
            if try_handle(self, "GET", path,
                          get_profile=lambda: api_mod._profile_from_token(api_mod._bearer_token(self)),
                          read_json=lambda: {}):
                return
        except Exception as exc:
            print(f"[api_mount] GET {path}: {exc}")
        return _orig_get(self)

    def do_POST(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        try:
            if try_handle(self, "POST", path,
                          get_profile=lambda: api_mod._profile_from_token(api_mod._bearer_token(self)),
                          read_json=lambda: api_mod._body(self)):
                return
        except Exception as exc:
            print(f"[api_mount] POST {path}: {exc}")
        return _orig_post(self)

    Handler.do_GET = do_GET
    Handler.do_POST = do_POST
    Handler._doof_v03_wrapped = True
    _installed = True
    print("[api_mount] DOOF v0.3 routes + hosted brain patch installed")
