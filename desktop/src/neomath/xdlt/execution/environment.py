"""Environment fingerprints for cache invalidation.

The hash covers the interpreter, platform and runner identity (and, cheaply, the
installed SymPy version). It deliberately avoids ``pip freeze`` so fingerprinting
stays fast.
"""

from __future__ import annotations

from neomath.xdlt.graph.hash import stable_hash

_RUNNER_IDENTITY = "neomath-xdlt-exec-1"


def environment_fingerprint() -> dict[str, str]:
    import platform
    import sys

    fingerprint: dict[str, str] = {
        "python": platform.python_version(),
        "platform": sys.platform,
        "runner": _RUNNER_IDENTITY,
    }
    try:
        import sympy as sp

        fingerprint["sympy"] = sp.__version__
    except Exception:  # noqa: BLE001 - environment probing is best-effort
        pass
    return fingerprint


def environment_hash() -> str:
    return stable_hash(environment_fingerprint())
