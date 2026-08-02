import random

import numpy as np
import pytest
import stringzilla as upstream

import mojostringzilla as sz


@pytest.mark.parametrize("text,needle", [
    ("abracadabra", "abra"), ("aaaaaa", "aaa"), ("", ""), ("abc", ""),
    ("naïve café", "fé"), (b"a\x00ba\x00b", b"\x00b"),
])
@pytest.mark.parametrize("start,end", [(0, None), (1, None), (-4, None), (0, -1), (99, None), (3, 2)])
def test_search_matches_upstream(text, needle, start, end):
    kwargs = {"start": start}
    if end is not None:
        kwargs["end"] = end
    assert sz.find(text, needle, **kwargs) == upstream.find(text, needle, **kwargs)
    assert sz.rfind(text, needle, **kwargs) == upstream.rfind(text, needle, **kwargs)
    assert sz.count(text, needle, **kwargs) == upstream.count(text, needle, **kwargs)
    assert sz.count(text, needle, allowoverlap=True, **kwargs) == upstream.count(text, needle, allowoverlap=True, **kwargs)
    assert sz.contains(text, needle, **kwargs) == upstream.contains(text, needle, **kwargs)


@pytest.mark.parametrize("text,chars", [("abracadabra", "ab"), ("", "x"), ("aaaa", "a"), (b"a\x00b", b"\x00"), ("abc", "")])
@pytest.mark.parametrize("start,end", [(0, None), (1, None), (-1, None), (0, -1), (99, None), (3, 2)])
def test_byteset_search_matches_upstream(text, chars, start, end):
    kwargs = {"start": start}
    if end is not None:
        kwargs["end"] = end
    for name in ("find_first_of", "find_first_not_of", "find_last_of", "find_last_not_of", "count_byteset"):
        assert getattr(sz, name)(text, chars, **kwargs) == getattr(upstream, name)(text, chars, **kwargs)


def test_prefix_suffix_and_equality_match_upstream():
    for text, needle in [("abracadabra", "abra"), ("abc", ""), ("", ""), (b"ab", b"b")]:
        for start, end in [(0, None), (1, None), (-2, None), (0, -1), (3, 2), (99, None)]:
            kwargs = {"start": start}
            if end is not None:
                kwargs["end"] = end
            assert sz.startswith(text, needle, **kwargs) == upstream.startswith(text, needle, **kwargs)
            assert sz.endswith(text, needle, **kwargs) == upstream.endswith(text, needle, **kwargs)
        assert sz.equal(text, text) == upstream.equal(text, text)


def test_split_partition_and_strip_match_upstream():
    text = "  alpha--beta--gamma  "
    for keep in (False, True):
        assert [str(x) for x in sz.split(text, "--", 1, keep)] == [str(x) for x in upstream.split(text, "--", 1, keep)]
        assert [str(x) for x in sz.rsplit(text, "--", 1, keep)] == [str(x) for x in upstream.rsplit(text, "--", 1, keep)]
        assert [str(x) for x in sz.split_byteset("a,b;c", ",;", 1, keep)] == [str(x) for x in upstream.split_byteset("a,b;c", ",;", 1, keep)]
    assert tuple(map(str, sz.partition(text, "--"))) == tuple(map(str, upstream.partition(text, "--")))
    assert tuple(map(str, sz.rpartition(text, "--"))) == tuple(map(str, upstream.rpartition(text, "--")))
    assert str(sz.strip(text)) == str(upstream.strip(text))
    assert str(sz.lstrip(text)) == str(upstream.lstrip(text))
    assert str(sz.rstrip(text)) == str(upstream.rstrip(text))


def test_splitlines_and_sorted_match_upstream():
    text = "a\r\nb\vc\n"
    for keep in (False, True):
        assert [str(x) for x in sz.splitlines(text, keep)] == [str(x) for x in upstream.splitlines(text, keep)]
    values = ["z", "aa", "b", "a", "", "é", "e", "aa"]
    assert [str(x) for x in sz.Strs(values).sorted()] == [str(x) for x in upstream.Strs(values).sorted()]


def test_ffi_buffers_are_nonempty_contiguous_and_int64_tables():
    empty = sz._lib.buffer(b"")
    assert empty.dtype == np.uint8
    assert empty.flags.c_contiguous and empty.size == 1 and sz._lib.addr(empty) != 0
    tape, offsets = sz.Strs([b"", b"a"])._tape()
    assert tape.dtype == np.uint8 and tape.flags.c_contiguous and sz._lib.addr(tape) != 0
    assert offsets.dtype == np.int64 and offsets.flags.c_contiguous


def test_str_methods_and_empty_separator_contract():
    ours, theirs = sz.Str("a,b,c"), upstream.Str("a,b,c")
    assert ours.find(",") == theirs.find(",")
    assert [str(x) for x in ours.split(",")] == [str(x) for x in theirs.split(",")]
    assert str(ours[:3]) == str(theirs[:3])
    with pytest.raises(ValueError):
        sz.split("abc", "")


def test_simd_block_boundaries_and_count_masks_match_upstream():
    text = b"x" * 31 + b"ab" + b"x" * 30 + b"the" + b"x" * 32 + b"the" + b"y" * 5
    for needle in (b"x", b"ab", b"the", b"missing"):
        assert sz.find(text, needle) == upstream.find(text, needle)
        assert sz.rfind(text, needle) == upstream.rfind(text, needle)
        assert sz.count(text, needle, allowoverlap=True) == upstream.count(text, needle, allowoverlap=True)


@pytest.mark.parametrize("reverse", [False, True])
def test_strs_argsort_matches_upstream(reverse):
    values = ["z", "aa", "b", "a", "", "é", "e", "aa"]
    ours = sz.Strs(values).argsort(reverse=reverse)
    theirs = upstream.Strs(values).argsort(reverse=reverse)
    assert sorted(ours) == sorted(theirs) == list(range(len(values)))
    assert [values[i] for i in ours] == [str(x) for x in upstream.Strs(values).sorted(reverse=reverse)]


def test_strs_argsort_randomized():
    rng = random.Random(0)
    alphabet = "abcde"
    for _ in range(30):
        values = ["".join(rng.choice(alphabet) for _ in range(rng.randrange(12))) for _ in range(100)]
        order = sz.Strs(values).argsort()
        assert sorted(order) == list(range(len(values)))
        assert [values[i] for i in order] == [str(x) for x in upstream.Strs(values).sorted()]
