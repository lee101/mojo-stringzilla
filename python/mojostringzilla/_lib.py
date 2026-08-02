"""ctypes loading and byte-buffer helpers for the Mojo shared library."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.environ.get("MOJO_STRINGZILLA_LIB") or os.path.join(ROOT, "dist", "libmojo-stringzilla.so")
I = ctypes.c_int64

_SIGNATURES = {
    "msz_find": ([I, I, I, I, I, I], I),
    "msz_rfind": ([I, I, I, I, I, I], I),
    "msz_count": ([I, I, I, I, I, I, I], I),
    "msz_first_of": ([I, I, I, I, I, I, I], I),
    "msz_last_of": ([I, I, I, I, I, I, I], I),
    "msz_count_of": ([I, I, I, I, I, I], I),
    "msz_equal": ([I, I, I, I], I),
    "msz_startswith": ([I, I, I, I, I, I], I),
    "msz_endswith": ([I, I, I, I, I, I], I),
    "msz_argsort": ([I, I, I, I, I], None),
}


def build(force: bool = False) -> str:
    source = os.path.join(ROOT, "src", "kernels.mojo")
    if not force and os.path.exists(LIB) and os.path.getmtime(LIB) >= os.path.getmtime(source):
        return LIB
    mojo = shutil.which("mojo")
    if not mojo:
        raise RuntimeError("mojo was not found; run through pixi or set MOJO_STRINGZILLA_LIB")
    library_dir = os.path.dirname(LIB)
    if library_dir:
        os.makedirs(library_dir, exist_ok=True)
    proc = subprocess.run([mojo, "build", "--emit", "shared-lib", source, "-o", LIB], text=True, capture_output=True, timeout=1800)
    if proc.returncode or not os.path.exists(LIB):
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return LIB


_handle: ctypes.CDLL | None = None


def lib() -> ctypes.CDLL:
    global _handle
    if _handle is None:
        _handle = ctypes.CDLL(build())
        for name, (argtypes, restype) in _SIGNATURES.items():
            fn = getattr(_handle, name)
            fn.argtypes, fn.restype = argtypes, restype
    return _handle


def buffer(data: bytes) -> np.ndarray:
    """A non-empty C-contiguous uint8 owner suitable for an address-only ABI."""
    return np.frombuffer(data if data else b"\0", dtype=np.uint8)


def addr(values: np.ndarray) -> int:
    return int(values.ctypes.data)
