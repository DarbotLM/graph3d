"""Native PDF reader: text/metadata extraction plus document-intelligence tools.

Implements enough of ISO 32000-1 to extract text without any third-party PDF
library: object tokenizer, classic xref tables, cross-reference streams
(PDF 1.5+) and object streams, FlateDecode/ASCIIHex/ASCII85/RunLength filters,
page-tree traversal, simple-font encoding resolution (StandardEncoding,
WinAnsiEncoding, MacRomanEncoding, plus /Differences overlays), and ToUnicode
CMap parsing for Type0/CID fonts. Falls back to a brute-force object scan when
the cross-reference table is missing or corrupt, mirroring the resilience
strategy every real-world PDF reader needs (many PDFs in the wild have broken
xrefs that Acrobat itself repairs on open).

The higher-level document-intelligence functions (summary, structure analysis,
document-type detection, text search, table-heuristic extraction, markdown
conversion) are a Python port of the algorithms in the Darbot PDF Viewer MCP
extension (github.com/darbotlabs/Darbot-PDF-Viewer-MCP, src/utils/pdf-processor.ts)
which operate on plain extracted text and therefore carry no binary-format
dependency at all.

Public API:
    extract_text(path) -> str                  page text joined by form-feed
    extract_pages(path) -> list[str]            per-page text (true page breaks)
    get_page_count(path) -> int
    extract_metadata(path) -> dict
    get_summary(path) -> str
    analyze_structure(path) -> dict
    detect_document_type(text) -> str
    search_text(path, term) -> list[dict]
    extract_tables(path) -> list[dict]
    to_markdown(path) -> str
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PdfError(ValueError):
    """Raised when a PDF cannot be parsed at all (not found, not a PDF, empty)."""


# ── Object model ────────────────────────────────────────────────────────────
# A parsed PDF object is one of: int, float, bool, None (null), bytes (string),
# str (name, WITHOUT the leading '/'), list (array), dict (dictionary), Ref
# (indirect reference), or Stream (dictionary + raw undecoded bytes).

@dataclass(frozen=True)
class Ref:
    num: int
    gen: int


@dataclass
class Stream:
    d: dict
    raw: bytes


_WHITESPACE = b"\x00\t\n\x0c\r "
_DELIMS = b"()<>[]{}/%"


def _is_ws(b: int) -> bool:
    return b in _WHITESPACE


def _is_delim(b: int) -> bool:
    return b in _DELIMS


def _collapse_refs(tokens: list) -> list:
    """Collapse ``N G R`` integer/integer/keyword triples into ``Ref`` objects.

    ``type(x) is int`` (not ``isinstance``) deliberately excludes ``bool``,
    which is a subclass of ``int`` in Python and would otherwise be misread
    as an object/generation number.
    """
    out: list = []
    i, n = 0, len(tokens)
    while i < n:
        if (i + 2 < n and type(tokens[i]) is int and type(tokens[i + 1]) is int
                and tokens[i + 2] == "R"):
            out.append(Ref(tokens[i], tokens[i + 1]))
            i += 3
        else:
            out.append(tokens[i])
            i += 1
    return out


class _Lexer:
    """Tokenizes the PDF object mini-language shared by the file body and by
    content streams (numbers, names, strings, arrays, dicts, refs, keywords).
    """

    __slots__ = ("data", "pos", "end")

    def __init__(self, data: bytes, pos: int = 0, end: int | None = None) -> None:
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def _skip_ws(self) -> None:
        data, end = self.data, self.end
        while self.pos < end:
            b = data[self.pos]
            if b == 0x25:  # '%' comment to end of line
                while self.pos < end and data[self.pos] not in b"\r\n":
                    self.pos += 1
            elif _is_ws(b):
                self.pos += 1
            else:
                break

    def peek_byte(self) -> int | None:
        return self.data[self.pos] if self.pos < self.end else None

    def read_token(self) -> Any:
        """Read one token: a Python value, a bare keyword str prefixed with
        '\\x00' sentinel is NOT used; keywords (obj/endobj/stream/R/true/...)
        are returned as plain str while names are returned wrapped so callers
        can tell a bare keyword ("R") from a PDF name ("/R"). We instead return
        names as ``_Name`` and keywords as plain ``str``.
        """
        self._skip_ws()
        if self.pos >= self.end:
            return None
        data = self.data
        b = data[self.pos]

        if b == 0x2F:  # '/'
            return self._read_name()
        if b == 0x28:  # '('
            return self._read_literal_string()
        if b == 0x3C:  # '<'
            if self.pos + 1 < self.end and data[self.pos + 1] == 0x3C:
                return self._read_dict_or_stream()
            return self._read_hex_string()
        if b == 0x5B:  # '['
            return self._read_array()
        if b in b"+-." or 0x30 <= b <= 0x39:
            return self._read_number()
        if b == 0x5D or b == 0x3E or b == 0x7D:  # ] > }  -- caller-consumed
            self.pos += 1
            return chr(b)
        return self._read_keyword()

    def _read_name(self) -> "_Name":
        data, end = self.data, self.end
        self.pos += 1  # skip '/'
        start = self.pos
        out = bytearray()
        while self.pos < end:
            b = data[self.pos]
            if _is_ws(b) or _is_delim(b):
                break
            if b == 0x23 and self.pos + 2 < end:  # '#XX' escape
                try:
                    out.append(int(data[self.pos + 1:self.pos + 3], 16))
                    self.pos += 3
                    continue
                except ValueError:
                    pass
            out.append(b)
            self.pos += 1
        del start
        return _Name(out.decode("latin-1"))

    def _read_number(self) -> int | float | str:
        data, end = self.data, self.end
        start = self.pos
        self.pos += 1
        saw_dot = data[start] == 0x2E
        while self.pos < end:
            b = data[self.pos]
            if 0x30 <= b <= 0x39:
                self.pos += 1
            elif b == 0x2E and not saw_dot:
                saw_dot = True
                self.pos += 1
            else:
                break
        text = data[start:self.pos].decode("ascii", errors="ignore")
        if not re.fullmatch(r"[+-]?\d*\.?\d*", text) or text in ("", "+", "-", "."):
            return text  # malformed numeric-ish token; treat as opaque keyword
        try:
            return float(text) if saw_dot else int(text)
        except ValueError:
            return 0

    def _read_literal_string(self) -> bytes:
        data, end = self.data, self.end
        self.pos += 1  # skip '('
        out = bytearray()
        depth = 1
        while self.pos < end:
            b = data[self.pos]
            if b == 0x5C:  # backslash escape
                self.pos += 1
                if self.pos >= end:
                    break
                e = data[self.pos]
                simple = {0x6E: 0x0A, 0x72: 0x0D, 0x74: 0x09, 0x62: 0x08,
                          0x66: 0x0C, 0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C}
                if e in simple:
                    out.append(simple[e])
                    self.pos += 1
                elif e in b"\r\n":  # line continuation, no output
                    self.pos += 1
                    if e == 0x0D and self.pos < end and data[self.pos] == 0x0A:
                        self.pos += 1
                elif 0x30 <= e <= 0x37:  # up to 3 octal digits
                    digits = data[self.pos:self.pos + 3]
                    n = 0
                    used = 0
                    for d in digits:
                        if 0x30 <= d <= 0x37 and used < 3:
                            n = n * 8 + (d - 0x30)
                            used += 1
                        else:
                            break
                    out.append(n & 0xFF)
                    self.pos += used
                else:
                    out.append(e)
                    self.pos += 1
                continue
            if b == 0x28:
                depth += 1
            elif b == 0x29:
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
            out.append(b)
            self.pos += 1
        return bytes(out)

    def _read_hex_string(self) -> bytes:
        data, end = self.data, self.end
        self.pos += 1  # skip '<'
        hexdigits = bytearray()
        while self.pos < end and data[self.pos] != 0x3E:
            b = data[self.pos]
            if not _is_ws(b):
                hexdigits.append(b)
            self.pos += 1
        self.pos += 1  # skip '>'
        if len(hexdigits) % 2:
            hexdigits.append(0x30)
        try:
            return bytes.fromhex(hexdigits.decode("ascii"))
        except ValueError:
            return b""

    def _read_array(self) -> list:
        self.pos += 1  # skip '['
        raw: list = []
        while True:
            self._skip_ws()
            if self.pos >= self.end or self.data[self.pos] == 0x5D:
                self.pos += 1
                break
            tok = self.read_token()
            if tok is None:
                break
            raw.append(tok)
        return _collapse_refs(raw)

    def _read_dict_or_stream(self) -> Any:
        self.pos += 2  # skip '<<'
        d: dict = {}
        while True:
            self._skip_ws()
            if self.pos + 1 < self.end and self.data[self.pos:self.pos + 2] == b">>":
                self.pos += 2
                break
            key = self.read_token()
            if not isinstance(key, _Name):
                break
            val = self._read_value_with_refs()
            d[key.value] = val
        self._skip_ws()
        if self.data[self.pos:self.pos + 6] == b"stream":
            self.pos += 6
            if self.data[self.pos:self.pos + 2] == b"\r\n":
                self.pos += 2
            elif self.data[self.pos:self.pos + 1] in (b"\n", b"\r"):
                self.pos += 1
            length = d.get("Length")
            body_start = self.pos
            if isinstance(length, int):
                body_end = min(body_start + length, self.end)
            else:
                body_end = self._find_endstream(body_start)
            raw = self.data[body_start:body_end]
            self.pos = body_end
            self._skip_ws()
            if self.data[self.pos:self.pos + 9] == b"endstream":
                self.pos += 9
            else:
                # /Length pointed at the wrong place (common in the wild):
                # re-anchor on the literal "endstream" marker instead.
                real_end = self._find_endstream(body_start)
                raw = self.data[body_start:real_end]
                self.pos = real_end
                if self.data[self.pos:self.pos + 9] == b"endstream":
                    self.pos += 9
            return Stream(d, raw)
        return d

    def _find_endstream(self, start: int) -> int:
        idx = self.data.find(b"endstream", start)
        if idx == -1:
            return self.end
        end = idx
        while end > start and self.data[end - 1] in b"\r\n":
            end -= 1
        return end

    def _read_value_with_refs(self) -> Any:
        tok = self.read_token()
        if type(tok) is int:
            save = self.pos
            self._skip_ws()
            gen = self.read_token()
            if type(gen) is int:
                save2 = self.pos
                self._skip_ws()
                kw = self.read_token()
                if kw == "R":
                    return Ref(tok, gen)
                self.pos = save2
            self.pos = save
        return tok

    def _read_keyword(self) -> str:
        data, end = self.data, self.end
        start = self.pos
        while self.pos < end and not _is_ws(data[self.pos]) and not _is_delim(data[self.pos]):
            self.pos += 1
        if self.pos == start:
            self.pos += 1
        word = data[start:self.pos].decode("latin-1")
        if word == "true":
            return True  # type: ignore[return-value]
        if word == "false":
            return False  # type: ignore[return-value]
        if word == "null":
            return None
        return word


class _Name(str):
    """Marker subclass so a parsed PDF /Name is distinguishable from a keyword."""
    @property
    def value(self) -> str:
        return str(self)


# ── Stream filters ──────────────────────────────────────────────────────────

def _apply_filters(stream: Stream) -> bytes:
    """Decode a stream's raw bytes through its /Filter chain.

    Only filters relevant to text/metadata are implemented (Flate, ASCIIHex,
    ASCII85, RunLength). Image-only filters (DCTDecode/JPXDecode/CCITTFax,
    LZWDecode) are left undecoded and skipped; they never carry page text.
    """
    filters = stream.d.get("Filter")
    params = stream.d.get("DecodeParms") or stream.d.get("DP")
    if filters is None:
        return stream.raw
    if not isinstance(filters, list):
        filters = [filters]
    if not isinstance(params, list):
        params = [params] * len(filters)
    data = stream.raw
    for i, f in enumerate(filters):
        name = str(f)
        p = params[i] if i < len(params) else None
        p = p if isinstance(p, dict) else {}
        if name in ("FlateDecode", "Fl"):
            data = _flate_decode(data, p)
        elif name in ("ASCIIHexDecode", "AHx"):
            data = _ascii_hex_decode(data)
        elif name in ("ASCII85Decode", "A85"):
            data = _ascii85_decode(data)
        elif name in ("RunLengthDecode", "RL"):
            data = _run_length_decode(data)
        else:
            break
    return data


def _flate_decode(data: bytes, params: dict) -> bytes:
    out = b""
    for attempt in (
        lambda: zlib.decompress(data),
        lambda: zlib.decompressobj().decompress(data),
        lambda: zlib.decompress(data, -zlib.MAX_WBITS),
    ):
        try:
            out = attempt()
            break
        except zlib.error:
            continue
    predictor = int(params.get("Predictor", 1) or 1)
    if predictor >= 10:
        out = _undo_png_predictor(out, params)
    elif predictor == 2:
        out = _undo_tiff_predictor(out, params)
    return out


def _undo_png_predictor(data: bytes, params: dict) -> bytes:
    columns = int(params.get("Columns", 1) or 1)
    colors = int(params.get("Colors", 1) or 1)
    bpc = int(params.get("BitsPerComponent", 8) or 8)
    bpp = max(1, (colors * bpc + 7) // 8)
    row_bytes = (columns * colors * bpc + 7) // 8
    out = bytearray()
    prev = bytearray(row_bytes)
    pos, n = 0, len(data)
    while pos + 1 + row_bytes <= n:
        tag = data[pos]
        row = bytearray(data[pos + 1:pos + 1 + row_bytes])
        pos += 1 + row_bytes
        for i in range(len(row)):
            a = row[i - bpp] if i >= bpp else 0
            up = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if tag == 1:
                row[i] = (row[i] + a) & 0xFF
            elif tag == 2:
                row[i] = (row[i] + up) & 0xFF
            elif tag == 3:
                row[i] = (row[i] + ((a + up) // 2)) & 0xFF
            elif tag == 4:
                row[i] = (row[i] + _paeth(a, up, c)) & 0xFF
        out.extend(row)
        prev = row
    return bytes(out)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _undo_tiff_predictor(data: bytes, params: dict) -> bytes:
    columns = int(params.get("Columns", 1) or 1)
    colors = int(params.get("Colors", 1) or 1)
    bpc = int(params.get("BitsPerComponent", 8) or 8)
    if bpc != 8:
        return data  # sub-byte TIFF predictor is rare in PDF text streams
    row_bytes = columns * colors
    out = bytearray(data)
    for r in range(0, len(out) - row_bytes + 1, row_bytes):
        row = out[r:r + row_bytes]
        for i in range(colors, len(row)):
            row[i] = (row[i] + row[i - colors]) & 0xFF
        out[r:r + row_bytes] = row
    return bytes(out)


def _ascii_hex_decode(data: bytes) -> bytes:
    end = data.find(b">")
    if end != -1:
        data = data[:end]
    hexstr = bytes(b for b in data if not _is_ws(b))
    if len(hexstr) % 2:
        hexstr += b"0"
    try:
        return bytes.fromhex(hexstr.decode("ascii"))
    except ValueError:
        return b""


def _ascii85_decode(data: bytes) -> bytes:
    end = data.find(b"~>")
    if end != -1:
        data = data[:end]
    data = bytes(b for b in data if not _is_ws(b))
    out = bytearray()
    group: list[int] = []
    for c in data:
        if c == 0x7A and not group:  # 'z' shorthand for four zero bytes
            out.extend(b"\x00\x00\x00\x00")
            continue
        group.append(c - 33)
        if len(group) == 5:
            val = 0
            for g in group:
                val = val * 85 + g
            out.extend(val.to_bytes(4, "big"))
            group = []
    if group:
        pad = 5 - len(group)
        group.extend([84] * pad)
        val = 0
        for g in group:
            val = val * 85 + g
        out.extend(val.to_bytes(4, "big")[:4 - pad])
    return bytes(out)


def _run_length_decode(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        length = data[i]
        i += 1
        if length == 128:
            break
        if length < 128:
            out.extend(data[i:i + length + 1])
            i += length + 1
        elif i < n:
            out.extend(bytes([data[i]]) * (257 - length))
            i += 1
    return bytes(out)


# ── Document: cross-reference resolution and object access ────────────────

class Document:
    """Parses a PDF's cross-reference structure and resolves indirect objects.

    Supports classic xref tables, cross-reference streams and object streams
    (PDF 1.5+), hybrid files (``/XRefStm`` in a classic trailer), and falls
    back to a brute-force ``N G obj`` scan when the xref chain is missing,
    truncated, or unreadable -- the same resilience strategy every real-world
    PDF reader needs, since a large fraction of PDFs in the wild have broken
    cross-reference tables that viewers silently repair on open.
    """

    def __init__(self, data: bytes) -> None:
        if not data.startswith(b"%PDF-"):
            # Some producers prepend junk bytes before the header; scan a
            # short window rather than rejecting the file outright.
            hdr = data.find(b"%PDF-", 0, 2048)
            if hdr == -1:
                raise PdfError("not a PDF file (missing %PDF- header)")
        self.data = data
        self.xref: dict[tuple[int, int], int] = {}
        self.compressed: dict[int, tuple[int, int]] = {}
        self.trailer: dict = {}
        self._cache: dict[tuple[int, int], Any] = {}
        self._objstm_cache: dict[int, tuple[bytes, list[tuple[int, int]], int]] = {}
        self._load_xref()

    # -- xref chain --------------------------------------------------------

    def _load_xref(self) -> None:
        try:
            self._load_xref_chain()
        except Exception:
            pass
        if "Root" not in self.trailer or not (self.xref or self.compressed):
            self._brute_force_scan()

    def _load_xref_chain(self) -> None:
        matches = list(re.finditer(rb"startxref\s+(\d+)", self.data))
        if not matches:
            raise PdfError("no startxref")
        offset: int | None = int(matches[-1].group(1))
        seen: set[int] = set()
        while offset is not None and offset not in seen and 0 <= offset < len(self.data):
            seen.add(offset)
            offset = self._load_xref_section(offset)

    def _load_xref_section(self, offset: int) -> int | None:
        lex = _Lexer(self.data, offset)
        lex._skip_ws()
        if self.data[lex.pos:lex.pos + 4] == b"xref":
            return self._load_classic_xref(lex)
        return self._load_xref_stream(offset)

    def _load_classic_xref(self, lex: _Lexer) -> int | None:
        lex.pos += 4
        while True:
            lex._skip_ws()
            if self.data[lex.pos:lex.pos + 7] == b"trailer":
                lex.pos += 7
                trailer = lex.read_token()
                if not isinstance(trailer, dict):
                    return None
                for k, v in trailer.items():
                    self.trailer.setdefault(k, v)
                xrefstm = trailer.get("XRefStm")
                if isinstance(xrefstm, int):
                    try:
                        self._load_xref_stream(xrefstm)
                    except Exception:
                        pass
                prev = trailer.get("Prev")
                return prev if isinstance(prev, int) else None
            start_tok = lex.read_token()
            if not isinstance(start_tok, int):
                return None
            count_tok = lex.read_token()
            if not isinstance(count_tok, int):
                return None
            for i in range(count_tok):
                off = lex.read_token()
                gen = lex.read_token()
                kw = lex.read_token()
                if not isinstance(off, int) or not isinstance(gen, int):
                    return None
                if kw == "n":
                    num = start_tok + i
                    self.xref.setdefault((num, gen), off)
                    self.xref.setdefault((num, 0), off)

    def _load_xref_stream(self, offset: int) -> int | None:
        obj = self._parse_object_at(offset)
        if not isinstance(obj, Stream):
            return None
        d = obj.d
        data = _apply_filters(obj)
        w = [int(x) for x in (d.get("W") or [1, 1, 1])]
        size = int(d.get("Size", 0) or 0)
        index = [int(x) for x in (d.get("Index") or [0, size])]
        rowlen = sum(w)
        pos = 0
        for k in range(0, len(index) - 1, 2):
            first, count = index[k], index[k + 1]
            for i in range(count):
                if pos + rowlen > len(data) or rowlen == 0:
                    break
                row = data[pos:pos + rowlen]
                pos += rowlen
                fields = []
                p = 0
                for width in w:
                    if width == 0:
                        fields.append(1 if len(fields) == 0 else 0)
                    else:
                        fields.append(int.from_bytes(row[p:p + width], "big"))
                        p += width
                num = first + i
                ftype, f2, f3 = fields[0], fields[1], fields[2]
                if ftype == 1:
                    self.xref.setdefault((num, f3), f2)
                    self.xref.setdefault((num, 0), f2)
                elif ftype == 2:
                    self.compressed.setdefault(num, (f2, f3))
        for k, v in d.items():
            self.trailer.setdefault(k, v)
        prev = d.get("Prev")
        return prev if isinstance(prev, int) else None

    def _brute_force_scan(self) -> None:
        """Last-resort recovery: scan the whole file for ``N G obj`` markers.

        Later matches win (an incrementally-updated PDF appends revised
        copies of objects at the end), which approximates the effect of a
        correct xref chain without needing one.
        """
        for m in re.finditer(rb"(?<![0-9])(\d{1,10})[ \t]+(\d{1,5})[ \t]+obj\b", self.data):
            num, gen, offset = int(m.group(1)), int(m.group(2)), m.start()
            self.xref[(num, gen)] = offset
            self.xref[(num, 0)] = offset
        if "Root" in self.trailer:
            return
        for tm in reversed(list(re.finditer(rb"trailer\b", self.data))):
            lex = _Lexer(self.data, tm.end())
            tok = lex.read_token()
            if isinstance(tok, dict) and "Root" in tok:
                for k, v in tok.items():
                    self.trailer.setdefault(k, v)
                break
        if "Root" not in self.trailer:
            for (num, gen) in sorted(self.xref):
                obj = self._parse_object_at(self.xref[(num, gen)])
                if isinstance(obj, dict) and obj.get("Type") == "Catalog":
                    self.trailer["Root"] = Ref(num, gen)
                    break

    # -- object access -------------------------------------------------------

    def _parse_object_at(self, offset: int) -> Any:
        lex = _Lexer(self.data, offset)
        num_tok = lex.read_token()
        gen_tok = lex.read_token()
        kw = lex.read_token()
        if kw != "obj" or not isinstance(num_tok, int) or not isinstance(gen_tok, int):
            return None
        return lex._read_value_with_refs()

    def resolve(self, obj: Any) -> Any:
        depth = 0
        while isinstance(obj, Ref) and depth < 64:
            obj = self.get_object(obj.num, obj.gen)
            depth += 1
        return obj

    def get_object(self, num: int, gen: int = 0) -> Any:
        key = (num, gen)
        if key in self._cache:
            return self._cache[key]
        self._cache[key] = None  # guards against reference cycles
        val = self._load_object(num, gen)
        self._cache[key] = val
        return val

    def _load_object(self, num: int, gen: int) -> Any:
        offset = self.xref.get((num, gen), self.xref.get((num, 0)))
        if offset is not None:
            return self._parse_object_at(offset)
        if num in self.compressed:
            stream_num, index = self.compressed[num]
            return self._load_from_object_stream(stream_num, index)
        return None

    def _load_from_object_stream(self, stream_num: int, index: int) -> Any:
        cached = self._objstm_cache.get(stream_num)
        if cached is None:
            stm = self.get_object(stream_num, 0)
            if not isinstance(stm, Stream):
                return None
            data = _apply_filters(stm)
            n = int(stm.d.get("N", 0) or 0)
            first = int(stm.d.get("First", 0) or 0)
            header = _Lexer(data, 0, first)
            pairs: list[tuple[int, int]] = []
            for _ in range(n):
                onum, ooff = header.read_token(), header.read_token()
                if not isinstance(onum, int) or not isinstance(ooff, int):
                    break
                pairs.append((onum, ooff))
            cached = (data, pairs, first)
            self._objstm_cache[stream_num] = cached
        data, pairs, first = cached
        if index >= len(pairs):
            return None
        _, rel_off = pairs[index]
        return _Lexer(data, first + rel_off)._read_value_with_refs()

    # -- document structure --------------------------------------------------

    def catalog(self) -> dict:
        root = self.resolve(self.trailer.get("Root"))
        return root if isinstance(root, dict) else {}

    def info(self) -> dict:
        info = self.resolve(self.trailer.get("Info"))
        return info if isinstance(info, dict) else {}

    def pages(self) -> list[dict]:
        """Flatten the page tree, merging inherited Resources/MediaBox/Rotate."""
        cat = self.catalog()
        out: list[dict] = []
        seen: set[int] = set()
        inheritable = ("Resources", "MediaBox", "CropBox", "Rotate")

        def walk(node: Any, inherited: dict, depth: int) -> None:
            if depth > 128 or not isinstance(node, dict) or id(node) in seen:
                return
            seen.add(id(node))
            merged = dict(inherited)
            for k in inheritable:
                if k in node:
                    merged[k] = node[k]
            kids = self.resolve(node.get("Kids"))
            if node.get("Type") == "Page" or (not isinstance(kids, list) and "Contents" in node):
                page = dict(node)
                for k in inheritable:
                    page.setdefault(k, merged.get(k))
                out.append(page)
                return
            for kid_ref in (kids or []):
                walk(self.resolve(kid_ref), merged, depth + 1)

        walk(self.resolve(cat.get("Pages")), {}, 0)
        if not out:
            # Root/Pages unreachable (typical after brute-force recovery of a
            # badly damaged file): fall back to any object that looks like a
            # standalone Page, in object-number order.
            for num, gen in sorted(self.xref):
                obj = self.get_object(num, gen)
                if isinstance(obj, dict) and obj.get("Type") == "Page":
                    out.append(obj)
        return out

    def page_content_bytes(self, page: dict) -> bytes:
        contents = self.resolve(page.get("Contents"))
        if isinstance(contents, Stream):
            return _apply_filters(contents)
        if isinstance(contents, list):
            parts = [_apply_filters(s) for c in contents
                     if isinstance(s := self.resolve(c), Stream)]
            return b"\n".join(parts)
        return b""


# ── Simple-font encodings ───────────────────────────────────────────────────
# The printable ASCII range (0x20-0x7E) is identical across StandardEncoding,
# WinAnsiEncoding, MacRomanEncoding and PDFDocEncoding by design (PDF 32000-1
# Annex D) -- only the upper range and a handful of control-adjacent codes
# differ. WinAnsiEncoding and MacRomanEncoding are (very nearly) Windows-1252
# and Mac OS Roman respectively, so Python's stdlib codecs give an accurate
# table for free with zero new dependencies.

def _codec_table(codec: str) -> tuple[str, ...]:
    out = []
    for b in range(256):
        try:
            out.append(bytes([b]).decode(codec))
        except UnicodeDecodeError:
            out.append("")
    return tuple(out)


def _standard_encoding_table() -> tuple[str, ...]:
    # ASCII range is shared; the upper range below covers the common Western
    # StandardEncoding assignments (quotes, dashes, ligatures, accents actually
    # seen in real-world Type1 fonts). Anything not covered degrades to an
    # empty glyph rather than a wrong one -- StandardEncoding is legacy and
    # rare in modern PDF output (superseded by WinAnsi/embedded+ToUnicode).
    table = list(_codec_table("ascii"))
    upper = {
        0o241: "\u00a1", 0o242: "\u00a2", 0o243: "\u00a3", 0o244: "\u2044",
        0o245: "\u00a5", 0o246: "\u0192", 0o247: "\u00a7", 0o250: "\u00a4",
        0o251: "'", 0o252: "\u201c", 0o253: "\u00ab", 0o254: "\u2039",
        0o255: "\u203a", 0o256: "\ufb01", 0o257: "\ufb02", 0o261: "\u2013",
        0o262: "\u2020", 0o263: "\u2021", 0o264: "\u00b7", 0o266: "\u00b6",
        0o267: "\u2022", 0o270: "\u201a", 0o271: "\u201e", 0o272: "\u201d",
        0o273: "\u00bb", 0o274: "\u2026", 0o275: "\u2030", 0o277: "\u00bf",
        0o301: "`", 0o302: "\u00b4", 0o303: "\u02c6", 0o304: "\u02dc",
        0o305: "\u00af", 0o306: "\u02d8", 0o307: "\u02d9", 0o310: "\u00a8",
        0o312: "\u02da", 0o313: "\u00b8", 0o315: "\u02dd", 0o316: "\u02db",
        0o317: "\u02c7", 0o320: "\u2014", 0o341: "\u00c6", 0o343: "\u00aa",
        0o350: "\u0141", 0o352: "\u00d8", 0o353: "\u0152", 0o354: "\u00ba",
        0o361: "\u00e6", 0o365: "\u0131", 0o370: "\u0142", 0o371: "\u00f8",
        0o372: "\u0153", 0o373: "\u00df",
    }
    for code, ch in upper.items():
        if code < len(table):
            table[code] = ch
    return tuple(table)


_STANDARD_ENCODING = _standard_encoding_table()
_BASE_ENCODINGS: dict[str, tuple[str, ...]] = {
    "StandardEncoding": _STANDARD_ENCODING,
    "WinAnsiEncoding": _codec_table("cp1252"),
    "MacRomanEncoding": _codec_table("mac_roman"),
    "PDFDocEncoding": _codec_table("cp1252"),  # close approximation
    "MacExpertEncoding": _STANDARD_ENCODING,   # rare; fall back rather than guess
}

# Adobe Glyph List subset for /Differences arrays: the glyph names that
# actually show up in practice (punctuation/typography glyphs). Any name
# matching uniXXXX / uXXXX(XX) is resolved generically from its hex codepoint
# without needing a table entry (covers most programmatically-subset fonts).
_GLYPH_TO_UNICODE: dict[str, str] = {
    "space": " ", "bullet": "\u2022", "endash": "\u2013", "emdash": "\u2014",
    "quoteleft": "\u2018", "quoteright": "\u2019", "quotedblleft": "\u201c",
    "quotedblright": "\u201d", "quotesinglbase": "\u201a", "quotedblbase": "\u201e",
    "ellipsis": "\u2026", "trademark": "\u2122", "copyright": "\u00a9",
    "registered": "\u00ae", "dagger": "\u2020", "daggerdbl": "\u2021",
    "section": "\u00a7", "paragraph": "\u00b6", "fi": "\ufb01", "fl": "\ufb02",
    "florin": "\u0192", "degree": "\u00b0", "plusminus": "\u00b1",
    "onehalf": "\u00bd", "onequarter": "\u00bc", "threequarters": "\u00be",
    "multiply": "\u00d7", "divide": "\u00f7", "nbspace": "\u00a0",
}
_UNI_GLYPH_RE = re.compile(r"^u(?:ni)?([0-9A-Fa-f]{4,6})$")


def _glyph_name_to_unicode(name: str, fallback: str) -> str:
    if name in _GLYPH_TO_UNICODE:
        return _GLYPH_TO_UNICODE[name]
    m = _UNI_GLYPH_RE.match(name)
    if m:
        try:
            return chr(int(m.group(1), 16))
        except (ValueError, OverflowError):
            pass
    return fallback


# ── ToUnicode CMap parsing (Type0/CID fonts) ────────────────────────────────
# Handles the bfchar/bfrange constructs every ToUnicode CMap uses (PDF 32000-1
# 9.10.3). Nested usecmap and non-Identity codespaceranges with mixed byte
# lengths are not modeled -- a documented limitation, not a silent wrong answer
# (unmapped codes are simply dropped from the extracted text).

_CMAP_BLOCK_RE = re.compile(
    rb"beginbfchar(.*?)endbfchar|beginbfrange(.*?)endbfrange", re.DOTALL
)
_HEX_RE = re.compile(rb"<([0-9A-Fa-f]+)>")
_BFRANGE_ENTRY_RE = re.compile(
    rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)"
)


def _cmap_hex_to_unicode(hexbytes: bytes) -> str:
    try:
        raw = bytes.fromhex(hexbytes.decode("ascii"))
    except ValueError:
        return ""
    if len(raw) % 2:
        raw += b"\x00"
    try:
        return raw.decode("utf-16-be")
    except UnicodeDecodeError:
        return ""


def _parse_tounicode_cmap(data: bytes) -> dict[int, str]:
    out: dict[int, str] = {}
    for m in _CMAP_BLOCK_RE.finditer(data):
        char_body, range_body = m.group(1), m.group(2)
        if char_body is not None:
            hexes = _HEX_RE.findall(char_body)
            for i in range(0, len(hexes) - 1, 2):
                out[int(hexes[i], 16)] = _cmap_hex_to_unicode(hexes[i + 1])
        elif range_body is not None:
            for entry in _BFRANGE_ENTRY_RE.finditer(range_body):
                lo, hi, dst = int(entry.group(1), 16), int(entry.group(2), 16), entry.group(3)
                if dst.startswith(b"["):
                    for offset, d in enumerate(_HEX_RE.findall(dst)):
                        if lo + offset > hi:
                            break
                        out[lo + offset] = _cmap_hex_to_unicode(d)
                else:
                    base = int(dst.strip(b"<>"), 16)
                    for code in range(lo, min(hi, lo + 65535) + 1):
                        out[code] = _cmap_hex_to_unicode(f"{base + (code - lo):04x}".encode())
    return out


# ── Font resolution ──────────────────────────────────────────────────────────

class _Font:
    __slots__ = ("code_to_unicode", "is_type0")

    def __init__(self) -> None:
        self.code_to_unicode: dict[int, str] | None = {}
        self.is_type0 = False

    def decode(self, raw: bytes) -> str:
        if self.is_type0:
            codes = [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw) - 1, 2)]
        else:
            codes = list(raw)
        if self.code_to_unicode is None:
            # Type0 with no ToUnicode and no better option: identity mapping.
            # Wrong for most real embedded fonts, but better than dropping
            # the glyph outright for the (rare) fonts where codes really are
            # Unicode-ish already.
            return "".join(chr(c) if 0x20 <= c < 0x110000 else "" for c in codes)
        return "".join(self.code_to_unicode.get(c, "") for c in codes)


def _build_font(doc: Document, font_dict: dict) -> _Font:
    f = _Font()
    subtype = str(font_dict.get("Subtype") or "")
    to_uni = doc.resolve(font_dict.get("ToUnicode"))
    to_uni_map = _parse_tounicode_cmap(_apply_filters(to_uni)) if isinstance(to_uni, Stream) else None

    if subtype == "Type0":
        f.is_type0 = True
        f.code_to_unicode = to_uni_map if to_uni_map else None
        return f

    if to_uni_map:
        f.code_to_unicode = to_uni_map
        return f

    base_table = _STANDARD_ENCODING
    encoding = doc.resolve(font_dict.get("Encoding"))
    diffs = None
    if isinstance(encoding, str):
        base_table = _BASE_ENCODINGS.get(encoding, _STANDARD_ENCODING)
    elif isinstance(encoding, dict):
        base_name = encoding.get("BaseEncoding")
        if isinstance(base_name, str):
            base_table = _BASE_ENCODINGS.get(base_name, _STANDARD_ENCODING)
        diffs = doc.resolve(encoding.get("Differences"))
    table = list(base_table)
    if isinstance(diffs, list):
        code = 0
        for item in diffs:
            item = doc.resolve(item)
            if isinstance(item, int):
                code = item
            elif isinstance(item, str) and 0 <= code < len(table):
                table[code] = _glyph_name_to_unicode(item, table[code])
                code += 1
    f.code_to_unicode = {i: ch for i, ch in enumerate(table) if ch}
    return f


# ── Content-stream text extraction ──────────────────────────────────────────

def _extract_page_text(doc: Document, page: dict) -> str:
    """Interpret a page's content stream well enough to recover reading-order
    text. Tracks BT/ET text-object boundaries, Tf (font selection), Td/TD/T*/Tm
    (treated as line breaks -- exact text-matrix math is unnecessary for plain
    text extraction), and Tj/TJ/'/" (show text, decoded through the active
    font's code->Unicode table). Graphics operators are ignored entirely.
    """
    content = doc.page_content_bytes(page)
    if not content:
        return ""
    resources = doc.resolve(page.get("Resources")) or {}
    font_res = doc.resolve(resources.get("Font")) or {}
    font_cache: dict[str, _Font] = {}

    def get_font(name: str) -> _Font:
        if name not in font_cache:
            fd = doc.resolve(font_res.get(name))
            font_cache[name] = _build_font(doc, fd) if isinstance(fd, dict) else _Font()
        return font_cache[name]

    out: list[str] = []
    line_has_text = False

    def newline() -> None:
        nonlocal line_has_text
        if out and out[-1] != "\n":
            out.append("\n")
        line_has_text = False

    def emit(s: str) -> None:
        nonlocal line_has_text
        if not s:
            return
        out.append(s)
        line_has_text = True

    cur_font: _Font | None = None
    in_text = False
    stack: list = []
    lex = _Lexer(content, 0)
    while lex.pos < lex.end:
        lex._skip_ws()
        if lex.pos >= lex.end:
            break
        b = lex.peek_byte()
        if b is None:
            break
        if b in (0x5B, 0x28, 0x2F, 0x3C) or b in b"+-." or 0x30 <= b <= 0x39:
            stack.append(lex.read_token())
            continue
        op = lex.read_token()
        if not isinstance(op, str):
            stack.append(op)
            continue
        if op == "BT":
            in_text = True
        elif op == "ET":
            in_text = False
        elif in_text and op == "Tf" and len(stack) >= 2 and isinstance(stack[-2], _Name):
            cur_font = get_font(str(stack[-2]))
        elif in_text and op in ("Td", "TD"):
            # Args are (tx, ty). PDF user space has +y up, so a meaningfully
            # negative ty moves to a new line below the current one. A
            # near-zero ty is an intra-line nudge (some producers position
            # every glyph with its own Td instead of a single Tj/TJ run) and
            # must NOT force a line break, or single words get shredded.
            ty = stack[-1] if len(stack) >= 2 and isinstance(stack[-1], (int, float)) else 0
            if ty < -0.01:
                newline()
        elif in_text and op in ("T*", "Tm"):
            newline()
        elif in_text and op == "Tj" and stack and isinstance(stack[-1], bytes) and cur_font:
            emit(cur_font.decode(stack[-1]))
        elif in_text and op in ("'", '"') and stack and isinstance(stack[-1], bytes):
            newline()
            if cur_font:
                emit(cur_font.decode(stack[-1]))
        elif in_text and op == "TJ" and stack and isinstance(stack[-1], list) and cur_font:
            for item in stack[-1]:
                if isinstance(item, bytes):
                    emit(cur_font.decode(item))
                elif isinstance(item, (int, float)) and item < -100 and out and not out[-1].endswith((" ", "\n")):
                    out.append(" ")
        stack.clear()

    text = "".join(out)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Text-string decoding (metadata values, not glyph codes) ─────────────────

def _decode_pdf_text_string(raw: bytes) -> str:
    """Decode a PDF 'text string' (Info dict values, per 7.9.2.2): either
    UTF-16BE with a leading BOM, or a single-byte encoding approximated well
    by cp1252 for the common Western-text case."""
    if raw[:2] == b"\xfe\xff":
        return raw[2:].decode("utf-16-be", errors="replace")
    if raw[:3] == b"\xef\xbb\xbf":  # nonstandard but occasionally seen
        return raw[3:].decode("utf-8", errors="replace")
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _text_value(info: dict, key: str) -> str | None:
    v = info.get(key)
    if isinstance(v, bytes):
        return _decode_pdf_text_string(v)
    return v if isinstance(v, str) else None


def _load(path: str | Path) -> tuple[Document, list[dict]]:
    doc = Document(Path(path).read_bytes())
    return doc, doc.pages()


# ── Public API ───────────────────────────────────────────────────────────────

def extract_pages(path: str | Path) -> list[str]:
    """Return one string of extracted text per page, in document order."""
    doc, pages = _load(path)
    return [_extract_page_text(doc, p) for p in pages]


def extract_text(path: str | Path) -> str:
    """Return the whole document's text, non-empty pages joined by a single
    newline. Matches the historical pypdf-based ``extract_pdf_text`` contract
    used elsewhere in graph3d (detect.py) so this is a drop-in replacement."""
    try:
        return "\n".join(t for t in extract_pages(path) if t)
    except Exception:
        return ""


def get_page_count(path: str | Path) -> int:
    _, pages = _load(path)
    return len(pages)


def extract_metadata(path: str | Path) -> dict:
    doc, pages = _load(path)
    info = doc.info()
    return {
        "title": _text_value(info, "Title") or "Unknown",
        "author": _text_value(info, "Author") or "Unknown",
        "subject": _text_value(info, "Subject") or "Unknown",
        "creator": _text_value(info, "Creator") or "Unknown",
        "producer": _text_value(info, "Producer") or "Unknown",
        "creation_date": _text_value(info, "CreationDate"),
        "modification_date": _text_value(info, "ModDate"),
        "pages": len(pages),
    }


# ── Document-intelligence layer ─────────────────────────────────────────────
# Ported from the Darbot PDF Viewer MCP extension's PdfProcessor
# (github.com/darbotlabs/Darbot-PDF-Viewer-MCP, src/utils/pdf-processor.ts),
# which computes these purely from extracted text + page count and therefore
# carries no binary-format dependency. Improved here to use graph3d.pdf's
# real per-page text (``extract_pages``) instead of that tool's form-feed
# splitting heuristic with a fallback to even character distribution across
# pages, which was needed there only because the wrapped pdf-parse library
# does not expose true page boundaries.

def get_summary(path: str | Path) -> str:
    """A short human/LLM-readable summary: title, author, page count, and a
    content sample -- suitable as MCP tool context."""
    meta = extract_metadata(path)
    full_text = extract_text(path)
    sample = full_text[:500] + "..." if len(full_text) > 500 else full_text
    return (
        "PDF Summary:\n"
        f"Title: {meta['title']}\n"
        f"Author: {meta['author']}\n"
        f"Pages: {meta['pages']}\n"
        f"Content Sample: {sample}"
    )


_HEADING_RE = re.compile(r"^\d+\.?\s")
_TABLE_LINE_RE = re.compile(r"\t{2,}|\t{1,}.*\t|[ ]{3,}.*[ ]{3,}| {3,}")


def detect_document_type(text: str) -> str:
    """Keyword-heuristic document classifier (academic paper, invoice, resume,
    legal document, book, financial report, or general document)."""
    lower = text.lower()
    if "abstract" in lower and "references" in lower:
        return "academic_paper"
    if "invoice" in lower or "bill" in lower or "amount due" in lower:
        return "invoice"
    if "resume" in lower or "curriculum vitae" in lower or "experience" in lower:
        return "resume"
    if "contract" in lower or "agreement" in lower or "terms and conditions" in lower:
        return "legal_document"
    if "chapter" in lower and "table of contents" in lower:
        return "book"
    if len(re.findall(r"\d+", lower)) > 50 and "total" in lower:
        return "financial_report"
    return "general_document"


def analyze_structure(path: str | Path) -> dict:
    """Word/line/paragraph counts, heading and table heuristics, and a
    document-type guess -- a lightweight structural fingerprint of the PDF."""
    meta = extract_metadata(path)
    text = extract_text(path)
    lines = [ln for ln in text.split("\n") if ln.strip()]
    words = [w for w in re.split(r"\s+", text) if w]
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    headings = [
        ln for ln in lines
        if 5 < len(ln.strip()) < 100 and (ln.strip() == ln.strip().upper() or _HEADING_RE.match(ln.strip()))
    ]
    tables = [ln for ln in lines if _TABLE_LINE_RE.search(ln)]
    pages = max(meta["pages"], 1)
    return {
        "pages": meta["pages"],
        "total_characters": len(text),
        "total_words": len(words),
        "total_lines": len(lines),
        "total_paragraphs": len(paragraphs),
        "potential_headings": len(headings),
        "potential_tables": len(tables),
        "average_words_per_page": round(len(words) / pages),
        "document_type": detect_document_type(text),
        "has_numbers": bool(re.search(r"\d", text)),
        "has_special_characters": bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", text)),
    }


def search_text(path: str | Path, term: str) -> list[dict]:
    """Search every page for *term* (case-insensitive), returning
    ``{"page": N, "position": offset, "context": "...surrounding text..."}``
    for each match, in page/position order."""
    if not term:
        return []
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    results: list[dict] = []
    for page_num, page_text in enumerate(extract_pages(path), start=1):
        for m in pattern.finditer(page_text):
            start = max(0, m.start() - 50)
            end = min(len(page_text), m.start() + len(term) + 50)
            results.append({
                "page": page_num,
                "position": m.start(),
                "context": page_text[start:end].strip(),
            })
    return results


def extract_tables(path: str | Path) -> list[dict]:
    """Heuristically identify table-like regions (rows with tab or wide
    multi-space column separators) and split them into cells. This is a
    best-effort layout heuristic, not a real table-structure parser."""
    tables: list[dict] = []
    for page_num, page_text in enumerate(extract_pages(path), start=1):
        table_lines = [ln for ln in page_text.split("\n") if _TABLE_LINE_RE.search(ln)]
        if len(table_lines) < 2:
            continue
        rows = []
        for ln in table_lines:
            cells = [c.strip() for c in re.split(r"\t+|[ ]{3,}", ln) if c.strip()]
            if len(cells) >= 2:
                rows.append(cells)
        if len(rows) >= 2:
            tables.append({"page": page_num, "table": rows})
    return tables


def to_markdown(path: str | Path) -> str:
    """Render the PDF as Markdown: a metadata header followed by the body
    text, with ALL-CAPS or numbered short lines promoted to ``##`` headings."""
    meta = extract_metadata(path)
    lines_out = [f"# {meta['title']}", ""]
    if meta["author"] != "Unknown":
        lines_out += [f"**Author:** {meta['author']}", ""]
    if meta["subject"] != "Unknown":
        lines_out += [f"**Subject:** {meta['subject']}", ""]
    lines_out += [f"**Pages:** {meta['pages']}", ""]
    if meta["creation_date"]:
        lines_out += [f"**Created:** {meta['creation_date']}", ""]
    lines_out += ["---", ""]

    for raw_line in extract_text(path).split("\n"):
        line = raw_line.strip()
        if not line:
            lines_out.append("")
            continue
        is_heading = len(line) < 100 and (
            line == line.upper() or _HEADING_RE.match(line) or re.match(r"^[A-Z][A-Z\s]{5,}$", line)
        )
        lines_out.append(f"## {line}" if is_heading else line)
        lines_out.append("")
    return "\n".join(lines_out)



