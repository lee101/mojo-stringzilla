"""Byte-string search and lexicographic ordering kernels exposed through C."""

from std.sys.info import simd_width_of

comptime BPtr = UnsafePointer[UInt8, AnyOrigin[mut=True]]
comptime IPtr = UnsafePointer[Int64, AnyOrigin[mut=True]]


def equal_at(text: BPtr, needle: BPtr, at: Int, n: Int) -> Bool:
    var i = 0
    comptime W = simd_width_of[DType.uint8]()
    while i + W <= n:
        if text.load[width=W](at + i) != needle.load[width=W](i):
            return False
        i += W
    while i < n:
        if text.load(at + i) != needle.load(i):
            return False
        i += 1
    return True


def in_set(value: UInt8, chars: BPtr, n: Int) -> Bool:
    var i = 0
    while i < n:
        if value == chars.load(i):
            return True
        i += 1
    return False


def find_impl(text: BPtr, text_n: Int, needle: BPtr, needle_n: Int, start: Int, end: Int) -> Int:
    if needle_n == 0:
        return start
    if needle_n > end - start:
        return -1
    var i = start
    var last = end - needle_n
    comptime W = simd_width_of[DType.uint8]()
    var first = SIMD[DType.uint8, W](needle.load(0))
    var final = SIMD[DType.uint8, W](needle.load(needle_n - 1))
    while i + W - 1 <= last:
        var candidates = text.load[width=W](i)
        var matches = candidates.eq(first) & text.load[width=W](i + needle_n - 1).eq(final)
        if matches:
            for lane in range(W):
                if matches[lane] and equal_at(text, needle, i + lane, needle_n):
                    return i + lane
        i += W
    while i <= last:
        if text.load(i) == needle.load(0) and text.load(i + needle_n - 1) == needle.load(needle_n - 1) and equal_at(text, needle, i, needle_n):
            return i
        i += 1
    return -1


def rfind_impl(text: BPtr, text_n: Int, needle: BPtr, needle_n: Int, start: Int, end: Int) -> Int:
    if needle_n == 0:
        return end
    if needle_n > end - start:
        return -1
    var i = end - needle_n
    comptime W = simd_width_of[DType.uint8]()
    var first = SIMD[DType.uint8, W](needle.load(0))
    var final = SIMD[DType.uint8, W](needle.load(needle_n - 1))
    while i - W + 1 >= start:
        var block = i - W + 1
        var matches = text.load[width=W](block).eq(first) & text.load[width=W](block + needle_n - 1).eq(final)
        if matches:
            for offset in range(W):
                var lane = W - 1 - offset
                if matches[lane] and equal_at(text, needle, block + lane, needle_n):
                    return block + lane
        i -= W
    while i >= start:
        if text.load(i) == needle.load(0) and text.load(i + needle_n - 1) == needle.load(needle_n - 1) and equal_at(text, needle, i, needle_n):
            return i
        i -= 1
    return -1


def compare_offsets(tape: BPtr, offsets: IPtr, left: Int, right: Int) -> Int:
    var left_start = Int(offsets.load(left))
    var left_end = Int(offsets.load(left + 1))
    var right_start = Int(offsets.load(right))
    var right_end = Int(offsets.load(right + 1))
    var shared = min(left_end - left_start, right_end - right_start)
    var i = 0
    while i < shared:
        var a = tape.load(left_start + i)
        var b = tape.load(right_start + i)
        if a >= 128 and b < 128:
            return -1
        if a < 128 and b >= 128:
            return 1
        if a < b:
            return -1
        if a > b:
            return 1
        i += 1
    if left_end - left_start < right_end - right_start:
        return -1
    if left_end - left_start > right_end - right_start:
        return 1
    return 0


def comes_after(tape: BPtr, offsets: IPtr, indices: IPtr, left: Int, right: Int, reverse: Int) -> Bool:
    var cmp = compare_offsets(tape, offsets, Int(indices.load(left)), Int(indices.load(right)))
    if cmp == 0:
        var left_index = Int(indices.load(left))
        var right_index = Int(indices.load(right))
        if left_index < right_index:
            cmp = -1
        elif left_index > right_index:
            cmp = 1
    return cmp < 0 if reverse != 0 else cmp > 0


def sift_down(tape: BPtr, offsets: IPtr, indices: IPtr, root_arg: Int, stop: Int, reverse: Int):
    var root = root_arg
    while root * 2 + 1 <= stop:
        var child = root * 2 + 1
        if child + 1 <= stop and comes_after(tape, offsets, indices, child + 1, child, reverse):
            child += 1
        if comes_after(tape, offsets, indices, child, root, reverse):
            var tmp = indices.load(root)
            indices.store(root, indices.load(child))
            indices.store(child, tmp)
            root = child
        else:
            return


@export("msz_find")
def msz_find(text_addr: Int, text_n: Int, needle_addr: Int, needle_n: Int, start: Int, end: Int) abi("C") -> Int:
    return find_impl(BPtr(unsafe_from_address=text_addr), text_n, BPtr(unsafe_from_address=needle_addr), needle_n, start, end)


@export("msz_rfind")
def msz_rfind(text_addr: Int, text_n: Int, needle_addr: Int, needle_n: Int, start: Int, end: Int) abi("C") -> Int:
    return rfind_impl(BPtr(unsafe_from_address=text_addr), text_n, BPtr(unsafe_from_address=needle_addr), needle_n, start, end)


@export("msz_count")
def msz_count(text_addr: Int, text_n: Int, needle_addr: Int, needle_n: Int, start: Int, end: Int, overlap: Int) abi("C") -> Int:
    var text = BPtr(unsafe_from_address=text_addr)
    var needle = BPtr(unsafe_from_address=needle_addr)
    if needle_n == 0:
        return end - start + 1
    var found = 0
    var at = start
    var last = end - needle_n
    if overlap != 0 and needle_n <= 3:
        comptime W = simd_width_of[DType.uint8]()
        var ones = SIMD[DType.uint8, W](1)
        var zeroes = SIMD[DType.uint8, W](0)
        var first = SIMD[DType.uint8, W](needle.load(0))
        while at + W - 1 <= last:
            var matches = text.load[width=W](at).eq(first)
            if needle_n >= 2:
                var final = SIMD[DType.uint8, W](needle.load(needle_n - 1))
                matches = matches & text.load[width=W](at + needle_n - 1).eq(final)
            if needle_n == 3:
                var middle = SIMD[DType.uint8, W](needle.load(1))
                matches = matches & text.load[width=W](at + 1).eq(middle)
            found += Int(matches.select(ones, zeroes).reduce_add()[0])
            at += W
    while at <= last:
        if text.load(at) == needle.load(0) and equal_at(text, needle, at, needle_n):
            found += 1
            at += 1 if overlap != 0 else needle_n
        else:
            at += 1
    return found


@export("msz_first_of")
def msz_first_of(text_addr: Int, text_n: Int, chars_addr: Int, chars_n: Int, start: Int, end: Int, invert: Int) abi("C") -> Int:
    var text = BPtr(unsafe_from_address=text_addr)
    var chars = BPtr(unsafe_from_address=chars_addr)
    var i = start
    while i < end:
        if in_set(text.load(i), chars, chars_n) != (invert != 0):
            return i
        i += 1
    return -1


@export("msz_last_of")
def msz_last_of(text_addr: Int, text_n: Int, chars_addr: Int, chars_n: Int, start: Int, end: Int, invert: Int) abi("C") -> Int:
    var text = BPtr(unsafe_from_address=text_addr)
    var chars = BPtr(unsafe_from_address=chars_addr)
    var i = end - 1
    while i >= start:
        if in_set(text.load(i), chars, chars_n) != (invert != 0):
            return i
        i -= 1
    return -1


@export("msz_count_of")
def msz_count_of(text_addr: Int, text_n: Int, chars_addr: Int, chars_n: Int, start: Int, end: Int) abi("C") -> Int:
    var text = BPtr(unsafe_from_address=text_addr)
    var chars = BPtr(unsafe_from_address=chars_addr)
    var found = 0
    var i = start
    while i < end:
        if in_set(text.load(i), chars, chars_n):
            found += 1
        i += 1
    return found


@export("msz_equal")
def msz_equal(left_addr: Int, left_n: Int, right_addr: Int, right_n: Int) abi("C") -> Int:
    if left_n != right_n:
        return 0
    return 1 if equal_at(BPtr(unsafe_from_address=left_addr), BPtr(unsafe_from_address=right_addr), 0, left_n) else 0


@export("msz_startswith")
def msz_startswith(text_addr: Int, text_n: Int, prefix_addr: Int, prefix_n: Int, start: Int, end: Int) abi("C") -> Int:
    if prefix_n > end - start:
        return 0
    return 1 if equal_at(BPtr(unsafe_from_address=text_addr), BPtr(unsafe_from_address=prefix_addr), start, prefix_n) else 0


@export("msz_endswith")
def msz_endswith(text_addr: Int, text_n: Int, suffix_addr: Int, suffix_n: Int, start: Int, end: Int) abi("C") -> Int:
    if suffix_n > end - start:
        return 0
    return 1 if equal_at(BPtr(unsafe_from_address=text_addr), BPtr(unsafe_from_address=suffix_addr), end - suffix_n, suffix_n) else 0


@export("msz_argsort")
def msz_argsort(tape_addr: Int, offsets_addr: Int, n: Int, indices_addr: Int, reverse: Int) abi("C"):
    if n < 2:
        return
    var tape = BPtr(unsafe_from_address=tape_addr)
    var offsets = IPtr(unsafe_from_address=offsets_addr)
    var indices = IPtr(unsafe_from_address=indices_addr)
    var i = n / 2 - 1
    while i >= 0:
        sift_down(tape, offsets, indices, i, n - 1, reverse)
        i -= 1
    var end = n - 1
    while end > 0:
        var tmp = indices.load(0)
        indices.store(0, indices.load(end))
        indices.store(end, tmp)
        sift_down(tape, offsets, indices, 0, end - 1, reverse)
        end -= 1
