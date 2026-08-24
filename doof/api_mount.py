"""Wrap Handler.do_GET / do_POST so /api/updates and /api/admin are live.

Call ``install()`` from ``run_server`` (or import this module from api).
"""
from __future__ import annotations

_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    try:
        from doof import api as api_mod
        from doof.api_extra import try_handle
    except Exception as e:
        print(f"[api_mount] skip: {e}")
        return

    Handler = getattr(api_mod, "Handler", None)
    if Handler is None:
        return

    _orig_get = Handler.do_GET
    _orig_post = Handler.do_POST

    def do_GET(self):  # type: ignore[no-untyped-def]
        from urllib.parse import urlparse

        path = urlparse(self.path).path
        try:
            if try_handle(
                self,
                "GET",
                path,
                get_profile=lambda: api_mod._profile_from_token(api_mod._bearer_token(self)),
                read_json=lambda: {},
            ):
                return
        except Exception as e:
            print(f"[api_mount] GET {path}: {e}")
        return _orig_get(self)

    def do_POST(self):  # type: ignore[no-untyped-def]
        from urllib.parse import urlparse

        path = urlparse(self.path).path
        try:
            if try_handle(
                self,
                "POST",
                path,
                get_profile=lambda: api_mod._profile_from_token(api_mod._bearer_token(self)),
                read_json=lambda: api_mod._body(self),
            ):
                return
        except Exception as e:
            print(f"[api_mount] POST {path}: {e}")
        return _orig_post(self)

    Handler.do_GET = do_GET  # type: ignore[method-assign]
    Handler.do_POST = do_POST  # type: ignore[method-assign]
    _installed = True
    print("[api_mount] updates + admin routes mounted")
