"""A focused Mojo implementation of stringzilla's byte-string primitives."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from typing import Any

import numpy as np

from . import _lib

__version__ = "0.1.0"


def _bytes(value: str | bytes | bytearray | memoryview | "Str") -> bytes:
    if isinstance(value, Str):
        return value._data
    if isinstance(value, str):
        return value.encode()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    raise TypeError("expected str, bytes, bytearray, memoryview, or Str")


def _bounds(n: int, start: int = 0, end: int | None = None) -> tuple[int, int]:
    start, end, _ = slice(start, end).indices(n)
    return start, end


def _call(name: str, text: bytes, other: bytes, start: int = 0, end: int | None = None, extra: int | None = None) -> int:
    begin, finish = _bounds(len(text), start, end)
    a, b = _lib.buffer(text), _lib.buffer(other)
    args: list[int] = [_lib.addr(a), len(text), _lib.addr(b), len(other), begin, finish]
    if extra is not None:
        args.append(extra)
    return int(getattr(_lib.lib(), name)(*args))


def find(text: Any, substring: Any, start: int = 0, end: int | None = None) -> int:
    data, needle = _bytes(text), _bytes(substring)
    begin, finish = _bounds(len(data), start, end)
    if not needle:
        return min(begin, finish)
    return _call("msz_find", data, needle, start, end)


def rfind(text: Any, substring: Any, start: int = 0, end: int | None = None) -> int:
    data, needle = _bytes(text), _bytes(substring)
    if not needle:
        return _bounds(len(data), start, end)[1]
    return _call("msz_rfind", data, needle, start, end)


def count(text: Any, substring: Any, start: int = 0, end: int | None = None, allowoverlap: bool = False) -> int:
    data, needle = _bytes(text), _bytes(substring)
    if not needle:
        return 0
    return _call("msz_count", data, needle, start, end, int(allowoverlap))


def contains(text: Any, substring: Any, start: int = 0, end: int | None = None) -> bool:
    return find(text, substring, start, end) >= 0


def equal(first: Any, second: Any) -> bool:
    left, right = _bytes(first), _bytes(second)
    a, b = _lib.buffer(left), _lib.buffer(right)
    return bool(_lib.lib().msz_equal(_lib.addr(a), len(left), _lib.addr(b), len(right)))


def startswith(text: Any, prefix: Any, start: int = 0, end: int | None = None) -> bool:
    data, prefix_data = _bytes(text), _bytes(prefix)
    # Upstream accepts an empty prefix even when the requested range is empty
    # or inverted.
    if not prefix_data:
        return True
    return bool(_call("msz_startswith", data, prefix_data, start, end))


def endswith(text: Any, suffix: Any, start: int = 0, end: int | None = None) -> bool:
    data = _bytes(text)
    # Upstream treats negative ends as the default full extent and does not
    # constrain a suffix by start. An inverted explicit range also falls back
    # to the full extent.
    finish = len(data) if end is None or end < 0 or start > end else min(end, len(data))
    return bool(_call("msz_endswith", data, _bytes(suffix), 0, finish))


def find_first_of(text: Any, chars: Any, start: int = 0, end: int | None = None) -> int:
    data, char_data = _bytes(text), _bytes(chars)
    if not char_data:
        begin, finish = _bounds(len(data), start, end)
        return min(begin, finish)
    return _call("msz_first_of", data, char_data, start, end, 0)


def find_first_not_of(text: Any, chars: Any, start: int = 0, end: int | None = None) -> int:
    data, char_data = _bytes(text), _bytes(chars)
    if not char_data:
        begin, finish = _bounds(len(data), start, end)
        return min(begin, finish)
    return _call("msz_first_of", data, char_data, start, end, 1)


def find_last_of(text: Any, chars: Any, start: int = 0, end: int | None = None) -> int:
    data, char_data = _bytes(text), _bytes(chars)
    if not char_data:
        return _bounds(len(data), start, end)[1]
    return _call("msz_last_of", data, char_data, start, end, 0)


def find_last_not_of(text: Any, chars: Any, start: int = 0, end: int | None = None) -> int:
    data, char_data = _bytes(text), _bytes(chars)
    if not char_data:
        return _bounds(len(data), start, end)[1]
    return _call("msz_last_of", data, char_data, start, end, 1)


def count_byteset(text: Any, chars: Any, start: int = 0, end: int | None = None) -> int:
    data = _bytes(text)
    begin, finish = _bounds(len(data), start, end)
    char_data = _bytes(chars)
    a, b = _lib.buffer(data), _lib.buffer(char_data)
    return int(_lib.lib().msz_count_of(_lib.addr(a), len(data), _lib.addr(b), len(char_data), begin, finish))


def index(text: Any, substring: Any, start: int = 0, end: int | None = None) -> int:
    result = find(text, substring, start, end)
    if result < 0:
        raise ValueError("substring not found")
    return result


def rindex(text: Any, substring: Any, start: int = 0, end: int | None = None) -> int:
    result = rfind(text, substring, start, end)
    if result < 0:
        raise ValueError("substring not found")
    return result


def _pieces(data: bytes, separator: bytes, maxsplit: int, reverse: bool, keepseparator: bool) -> list[bytes]:
    if not separator:
        raise ValueError("empty separator")
    result: list[bytes] = []
    if reverse:
        stop = len(data)
        while maxsplit < 0 or len(result) < maxsplit:
            at = rfind(data, separator, 0, stop)
            if at < 0:
                break
            result.append(data[at if keepseparator else at + len(separator):stop])
            stop = at
        result.append(data[:stop])
        result.reverse()
        return result
    begin = 0
    while maxsplit < 0 or len(result) < maxsplit:
        at = find(data, separator, begin)
        if at < 0:
            break
        result.append(data[begin:at + (len(separator) if keepseparator else 0)])
        begin = at + len(separator)
    result.append(data[begin:])
    return result


def split(text: Any, separator: Any, maxsplit: int = -1, keepseparator: bool = False) -> "Strs":
    return Strs(_pieces(_bytes(text), _bytes(separator), maxsplit, False, keepseparator))


def rsplit(text: Any, separator: Any, maxsplit: int = -1, keepseparator: bool = False) -> "Strs":
    return Strs(_pieces(_bytes(text), _bytes(separator), maxsplit, True, keepseparator))


def split_byteset(text: Any, separators: Any, maxsplit: int = -1, keepseparator: bool = False) -> "Strs":
    data, chars = _bytes(text), _bytes(separators)
    result: list[bytes] = []
    begin = 0
    while maxsplit < 0 or len(result) < maxsplit:
        at = find_first_of(data, chars, begin)
        if at < 0:
            break
        result.append(data[begin:at + (1 if keepseparator else 0)])
        begin = at + 1
    result.append(data[begin:])
    return Strs(result)


def partition(text: Any, separator: Any) -> tuple["Str", "Str", "Str"]:
    data, sep = _bytes(text), _bytes(separator)
    at = find(data, sep)
    if at < 0:
        return Str(data), Str(b""), Str(b"")
    return Str(data[:at]), Str(sep), Str(data[at + len(sep):])


def rpartition(text: Any, separator: Any) -> tuple["Str", "Str", "Str"]:
    data, sep = _bytes(text), _bytes(separator)
    at = rfind(data, sep)
    if at < 0:
        return Str(b""), Str(b""), Str(data)
    return Str(data[:at]), Str(sep), Str(data[at + len(sep):])


def splitlines(text: Any, keeplinebreaks: bool = False, maxsplit: int = -1) -> "Strs":
    data = _bytes(text)
    # stringzilla treats every byte line separator independently and retains a
    # final empty field, unlike Python's bytes.splitlines().
    separators = b"\n\r\v\f\x1c\x1d\x1e\x85"
    result: list[bytes] = []
    begin = 0
    while maxsplit < 0 or len(result) < maxsplit:
        at = find_first_of(data, separators, begin)
        if at < 0:
            break
        result.append(data[begin:at + int(keeplinebreaks)])
        begin = at + 1
    result.append(data[begin:])
    return Strs(result)


def strip(text: Any, chars: Any | None = None) -> "Str":
    return Str(_bytes(text).strip(None if chars is None else _bytes(chars)))


def lstrip(text: Any, chars: Any | None = None) -> "Str":
    return Str(_bytes(text).lstrip(None if chars is None else _bytes(chars)))


def rstrip(text: Any, chars: Any | None = None) -> "Str":
    return Str(_bytes(text).rstrip(None if chars is None else _bytes(chars)))


class Str:
    """Immutable byte string with stringzilla-compatible search methods."""

    __slots__ = ("_data",)

    def __init__(self, source: Any = b"") -> None:
        self._data = _bytes(source)

    def __str__(self) -> str:
        return self._data.decode()

    def __repr__(self) -> str:
        return f"sz.Str({str(self)!r})"

    def __bytes__(self) -> bytes:
        return self._data

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return hash(self._data)

    def __eq__(self, other: object) -> bool:
        try:
            return equal(self, other)
        except TypeError:
            return False

    def __contains__(self, item: Any) -> bool:
        return contains(self, item)

    def __getitem__(self, key: int | slice) -> int | "Str":
        value = self._data[key]
        return Str(value) if isinstance(key, slice) else value

    def decode(self, *args: Any, **kwargs: Any) -> str:
        return self._data.decode(*args, **kwargs)

    nbytes = property(lambda self: len(self._data))
    find = lambda self, *a, **kw: find(self, *a, **kw)
    rfind = lambda self, *a, **kw: rfind(self, *a, **kw)
    count = lambda self, *a, **kw: count(self, *a, **kw)
    contains = lambda self, *a, **kw: contains(self, *a, **kw)
    index = lambda self, *a, **kw: index(self, *a, **kw)
    rindex = lambda self, *a, **kw: rindex(self, *a, **kw)
    startswith = lambda self, *a, **kw: startswith(self, *a, **kw)
    endswith = lambda self, *a, **kw: endswith(self, *a, **kw)
    find_first_of = lambda self, *a, **kw: find_first_of(self, *a, **kw)
    find_first_not_of = lambda self, *a, **kw: find_first_not_of(self, *a, **kw)
    find_last_of = lambda self, *a, **kw: find_last_of(self, *a, **kw)
    find_last_not_of = lambda self, *a, **kw: find_last_not_of(self, *a, **kw)
    count_byteset = lambda self, *a, **kw: count_byteset(self, *a, **kw)
    split = lambda self, *a, **kw: split(self, *a, **kw)
    rsplit = lambda self, *a, **kw: rsplit(self, *a, **kw)
    partition = lambda self, *a, **kw: partition(self, *a, **kw)
    rpartition = lambda self, *a, **kw: rpartition(self, *a, **kw)
    splitlines = lambda self, *a, **kw: splitlines(self, *a, **kw)
    strip = lambda self, *a, **kw: strip(self, *a, **kw)
    lstrip = lambda self, *a, **kw: lstrip(self, *a, **kw)
    rstrip = lambda self, *a, **kw: rstrip(self, *a, **kw)


class Strs(Sequence[Str]):
    """A compact string tape with Mojo-backed lexicographic argsort."""

    def __init__(self, sequence: Iterable[Any], view: bool = False) -> None:
        del view
        values = [_bytes(item) for item in sequence]
        self._values = values

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[Str]:
        return (Str(item) for item in self._values)

    def __getitem__(self, key: int | slice) -> Str | "Strs":
        if isinstance(key, slice):
            return Strs(self._values[key])
        return Str(self._values[key])

    def __repr__(self) -> str:
        return f"sz.Strs({[str(item) for item in self]!r})"

    def _tape(self) -> tuple[np.ndarray, np.ndarray]:
        offsets = np.empty(len(self._values) + 1, dtype=np.int64)
        offsets[0] = 0
        for i, value in enumerate(self._values):
            offsets[i + 1] = offsets[i] + len(value)
        return _lib.buffer(b"".join(self._values)), offsets

    def argsort(self, reverse: bool = False) -> tuple[int, ...]:
        tape, offsets = self._tape()
        indices = np.arange(len(self._values), dtype=np.int64)
        if len(indices):
            _lib.lib().msz_argsort(_lib.addr(tape), _lib.addr(offsets), len(indices), _lib.addr(indices), int(reverse))
        return tuple(int(i) for i in indices)

    def sorted(self, reverse: bool = False) -> "Strs":
        return Strs((self._values[i] for i in self.argsort(reverse)))


__all__ = [
    "Str", "Strs", "contains", "count", "count_byteset", "endswith", "equal", "find",
    "find_first_not_of", "find_first_of", "find_last_not_of", "find_last_of", "index", "lstrip",
    "partition", "rfind", "rindex", "rpartition", "rsplit", "rstrip", "split", "split_byteset",
    "splitlines", "startswith", "strip",
]
