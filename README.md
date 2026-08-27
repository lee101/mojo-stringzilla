# mojo-stringzilla

`mojo-stringzilla` is a focused, standalone Mojo port of the compute-bound byte-string
operations in [stringzilla](https://pypi.org/project/stringzilla/): substring search,
byte-set search, counting, prefix/suffix tests, and lexicographic `Strs.argsort`.
Its Python API is intentionally shaped like upstream, so covered calls migrate by changing
the import:

```python
import mojostringzilla as sz

text = sz.Str("error=503 path=/v1/items\nerror=200 path=/health")
assert text.find("path=/v1") == 10
assert text.count("error=") == 2
assert sz.Strs(["z", "aa", "b"]).argsort() == (1, 2, 0)
```

## Covered subset

`Str` and module-level `find`, `rfind`, `count` (including overlap), `contains`, `equal`,
`startswith`, `endswith`, the four `find_*_of` operations, `count_byteset`, `index`,
`rindex`, `split`, `rsplit`, `split_byteset`, `partition`, `rpartition`, `splitlines`, and
ASCII byte `strip` variants are available. `Strs.argsort()` and `Strs.sorted()` use a Mojo
heapsort over one contiguous UTF-8 tape and an int64 offset table.

Not covered: StringTape/Arrow views, hashing and crypto, random generation, translation,
and the Unicode-specific case-folding, word, and iterator APIs. Those need different data
and Unicode contracts than this byte-oriented kernel set.

## Install and verify

From a checkout, use the pinned Pixi environment. This project does not currently publish a
wheel: the shared library is built locally for the active machine.

```bash
pixi install
pixi run build
pixi run test
pixi run bench
```

## Benchmarks

Measured with `pixi run bench` on an Intel Xeon E5-2697 v4 (Linux 6.8, single-threaded
calls). Substring search, short-overlap counting, and byte-set scans use host-width SIMD;
the packed-tape sort also wins on this input.

| kernel | mojo-stringzilla | stringzilla | ratio |
| --- | ---: | ---: | ---: |
| find miss, 9 MB haystack | 0.49 ms | 0.73 ms | 1.47x faster |
| rfind miss, 9 MB haystack | 0.52 ms | 0.76 ms | 1.45x faster |
| count overlap, 9 MB haystack | 0.91 ms | 5.70 ms | 6.25x faster |
| find first of miss, 9 MB haystack | 0.66 ms | 0.66 ms | 1.00x slower |
| find last of miss, 9 MB haystack | 0.72 ms | 7.33 ms | 10.18x faster |
| count byteset, 9 MB haystack | 1.29 ms | 47.35 ms | 36.59x faster |
| argsort, 80k strings | 80.33 ms | 167.07 ms | 2.08x faster |

## How it works

Python UTF-8 encodes each input and passes its non-null NumPy byte-buffer address and length
through `ctypes`. The C ABI exports take `Int` addresses, reconstruct mutable-origin Mojo
pointers, and never allocate. Search uses host-width SIMD masks to skip blocks with no matching
first and last byte, then verifies only candidate lanes and handles the scalar tail. Overlapping
counts for one-, two-, and three-byte needles reduce exact SIMD match masks directly. Byte-set
search and counting combine one comparison mask per requested byte, reduce full vectors, and
retain a scalar remainder loop. For bulk ordering, Python packs all values into one tape plus an
`int64` offsets array; Mojo heapsorts an index array, so the byte data is never copied during the
sort.

No GPU path is included: search, counting, and comparison-based ordering are memory-bound, so
transfer and launch overhead outweigh useful parallel work for these kernels. The scans also
remain serial: ordered searches benefit from early exit, while threading the now memory-bound
full scans would add launch and reduction overhead.

The library is built as `dist/libmojo-stringzilla.so` from a single Mojo compilation unit. That
keeps compilation centralized while the Python API makes one native call per search primitive.
