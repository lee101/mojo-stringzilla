"""Measure mojo-stringzilla against the native upstream package."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import mojostringzilla as sz
import stringzilla as upstream


def best(fn, repeat=4):
    result = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        result = min(result, time.perf_counter() - t0)
    return result


def row(name, ours, theirs):
    ratio = theirs / ours
    status = "faster" if ratio > 1 else "slower"
    print(f"| {name} | {ours * 1e3:.2f} ms | {theirs * 1e3:.2f} ms | {ratio:.2f}x {status} |")


def main():
    text = ("the quick brown fox jumps over the lazy dog / " * 200_000).encode()
    needle = b"a token that is absent"
    values = [f"{(i * 48271) % 2_147_483_647:010d}-value" for i in range(80_000, 0, -1)]
    print("| kernel | mojo-stringzilla | stringzilla | ratio |")
    print("| --- | ---: | ---: | ---: |")
    row("find miss, 9 MB haystack", best(lambda: sz.find(text, needle)), best(lambda: upstream.find(text, needle)))
    row("rfind miss, 9 MB haystack", best(lambda: sz.rfind(text, needle)), best(lambda: upstream.rfind(text, needle)))
    row("count overlap, 9 MB haystack", best(lambda: sz.count(text, b"the", allowoverlap=True)), best(lambda: upstream.count(text, b"the", allowoverlap=True)))
    row("find first of miss, 9 MB haystack", best(lambda: sz.find_first_of(text, b"XYZ")), best(lambda: upstream.find_first_of(text, b"XYZ")))
    row("find last of miss, 9 MB haystack", best(lambda: sz.find_last_of(text, b"XYZ")), best(lambda: upstream.find_last_of(text, b"XYZ")))
    row("count byteset, 9 MB haystack", best(lambda: sz.count_byteset(text, b"aeiou")), best(lambda: upstream.count_byteset(text, b"aeiou")))
    row("argsort, 80k strings", best(lambda: sz.Strs(values).argsort()), best(lambda: upstream.Strs(values).argsort()))


if __name__ == "__main__":
    main()
