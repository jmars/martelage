#!/usr/bin/env python3
"""Extract text (and run geometry) from the PDF that Typst 0.15 emits.

Why this exists: no pdftotext, mutool, qpdf or gs is installed on this host, so the
content-completeness gate needs an instrument of its own. This one is narrow on
purpose -- it understands the shapes Typst actually writes (uncompressed object
headers, FlateDecode content streams, Identity-H Type0 fonts with a ToUnicode CMap,
`q`/`Q`/`cm` positioning) and raises PDFError on anything it does not.

Usage:
    python3 tools/pdftext.py FILE.pdf            # text, one line per rendered line, \\f per page
    python3 tools/pdftext.py FILE.pdf --runs     # JSON: every show-run with page/x/y/size/text
    python3 tools/pdftext.py FILE.pdf --json     # JSON: list of rendered lines (pages split by \\f)

Known limitation (stated, not hidden): a rendered line with no glyphs -- a blank line
inside a pasted code block -- produces no show-run, so it is invisible here. Blank-line
structure is verified against the .typ source instead, which carries it byte-exactly.
"""

import json
import re
import sys
import zlib


class PDFError(Exception):
    pass


_TOK = re.compile(
    rb"""<[0-9A-Fa-f\s]*>|\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)|/[^\s/<>\[\]()]+|[-+]?[0-9.]+|[A-Za-z*'"]+|[\[\]]""",
    re.S,
)


def _objects(data):
    objs = {}
    for m in re.finditer(rb"(?<![0-9])(\d+)\s+0\s+obj\b(.*?)\bendobj", data, re.S):
        objs[int(m.group(1))] = m.group(2)
    if not objs:
        raise PDFError("no objects found")
    return objs


def _stream(body):
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    head = body[:m.start()]
    end = body.find(b"endstream", m.end())
    if end < 0:
        raise PDFError("unterminated stream")
    raw = body[m.end():end]
    # /Length is authoritative, and stripping a trailing line ending instead is
    # wrong: a compressed stream may itself end with 0x0A or 0x0D, and eating
    # that byte leaves zlib an "incomplete or truncated stream". Measured on
    # this artifact -- one Flate stream in a 230 KB PDF ends with 0x0A, which
    # made this extractor refuse a PDF typst had written correctly.
    mlen = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", head)
    if mlen:
        n = int(mlen.group(1))
        if 0 <= n <= len(raw):
            raw = raw[:n]
    elif raw.endswith(b"\r\n"):
        raw = raw[:-2]
    elif raw.endswith(b"\n"):
        raw = raw[:-1]
    if b"/FlateDecode" in head:
        return zlib.decompress(raw)
    return raw


def _refs(s):
    return [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", s)]


def _utf16be(hexbytes):
    b = bytes.fromhex(hexbytes.decode())
    if len(b) % 2:
        return b.decode("latin-1")
    return b.decode("utf-16-be", "replace")


def _parse_cmap(text):
    cmap = {}
    for block in re.finditer(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block.group(1)):
            cmap[int(a, 16)] = _utf16be(b)
    for block in re.finditer(rb"beginbfrange(.*?)endbfrange", text, re.S):
        for a, b, rest in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", block.group(1)
        ):
            lo, hi = int(a, 16), int(b, 16)
            if rest.startswith(b"["):
                for i, it in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", rest)):
                    cmap[lo + i] = _utf16be(it)
            else:
                base = _utf16be(rest[1:-1])
                for i in range(hi - lo + 1):
                    cmap[lo + i] = base[:-1] + chr(ord(base[-1]) + i)
    return cmap


def _unescape_literal(raw):
    out = bytearray()
    i = 0
    esc = {b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12}
    while i < len(raw):
        c = raw[i:i + 1]
        if c == b"\\":
            n = raw[i + 1:i + 2]
            if n in esc:
                out.append(esc[n])
                i += 2
            elif n.isdigit():
                j = i + 1
                digits = b""
                while j < len(raw) and len(digits) < 3 and raw[j:j + 1].isdigit():
                    digits += raw[j:j + 1]
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
            elif n in (b"\n", b"\r"):
                i += 2
            else:
                out += n
                i += 2
        else:
            out += c
            i += 1
    return bytes(out)


def _decode(raw, cmap):
    if not cmap:
        return raw.decode("latin-1")
    return "".join(
        cmap.get((raw[i] << 8) | raw[i + 1], "\ufffd") for i in range(0, len(raw) - 1, 2)
    )


def _show(tok, cmap):
    if tok.startswith(b"<"):
        raw = bytes.fromhex(re.sub(rb"\s", b"", tok[1:-1]).decode())
    else:
        raw = _unescape_literal(tok[1:-1])
    return _decode(raw, cmap)


def runs(path):
    """Every text show-run in page order: (page, x, y, size, font, text)."""
    data = open(path, "rb").read()
    if not data.startswith(b"%PDF"):
        raise PDFError("not a PDF")
    objs = _objects(data)

    cat = next(
        (n for n, b in objs.items() if re.search(rb"/Type\s*/Catalog", b)),
        None,
    )
    if cat is None:
        raise PDFError("no catalog")
    root = _refs(re.search(rb"/Pages\s*(\d+\s+0\s+R)", objs[cat]).group(1))[0]

    pages = []

    def walk(n):
        body = objs[n]
        if re.search(rb"/Type\s*/Pages", body):
            for k in _refs(re.search(rb"/Kids\s*\[(.*?)\]", body, re.S).group(1)):
                walk(k)
        else:
            pages.append(n)

    walk(root)

    out = []
    for pi, pn in enumerate(pages):
        body = objs[pn]
        contents = re.search(rb"/Contents\s*(\d+\s+0\s+R|\[[^\]]*\])", body, re.S).group(1)
        cids = _refs(contents)
        if not cids:
            continue
        stream = b"\n".join(_stream(objs[c]) or b"" for c in cids)

        fonts = {}
        res = body
        rm = re.search(rb"/Resources\s+(\d+)\s+0\s+R", body)
        if rm:
            res = objs.get(int(rm.group(1)), b"")
        fm = re.search(rb"/Font\s*<<(.*?)>>", res, re.S)
        if not fm:
            fr = re.search(rb"/Font\s+(\d+)\s+0\s+R", res)
            if fr:
                fm = re.search(rb"<<(.*?)>>", objs.get(int(fr.group(1)), b""), re.S)
        if fm:
            for name, num in re.findall(rb"/([^\s/<>]+)\s+(\d+)\s+0\s+R", fm.group(1)):
                fbody = objs.get(int(num), b"")
                cm = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", fbody)
                fonts[name.decode()] = (
                    _parse_cmap(_stream(objs[int(cm.group(1))]) or b"") if cm else {}
                )

        cur, cur_size, cur_font = {}, 0.0, ""
        ctm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        ctm_stack = []
        pos_x, pos_y = 0.0, 0.0
        stack = []
        for tok in _TOK.findall(stream):
            if tok in (b"[", b"]"):
                continue
            if (
                tok.startswith(b"/")
                or tok[:1] in (b"<", b"(")
                or re.fullmatch(rb"[-+]?[0-9.]+", tok)
            ):
                stack.append(tok)
                continue
            op = tok.decode("latin-1", "replace")
            args, stack = stack, []
            nums = [float(a) for a in args if re.fullmatch(rb"[-+]?[0-9.]+", a)]
            if op == "q":
                ctm_stack.append(list(ctm))
            elif op == "Q":
                if ctm_stack:
                    ctm = ctm_stack.pop()
            elif op == "cm" and len(nums) >= 6:
                a, b, c, d, e, f = nums[-6:]
                ctm = [
                    a * ctm[0] + b * ctm[2],
                    a * ctm[1] + b * ctm[3],
                    c * ctm[0] + d * ctm[2],
                    c * ctm[1] + d * ctm[3],
                    e * ctm[0] + f * ctm[2] + ctm[4],
                    e * ctm[1] + f * ctm[3] + ctm[5],
                ]
            elif op in ("Tm", "Td", "TD") and len(nums) >= 2:
                pos_y = nums[-1] * ctm[3] + ctm[5]
                pos_x = nums[-2] * ctm[0] + ctm[4]
            elif op == "Tf":
                for a in reversed(args):
                    if a.startswith(b"/"):
                        cur_font = a[1:].decode()
                        cur = fonts.get(cur_font, {})
                        break
                if nums:
                    cur_size = nums[-1]
            elif op in ("Tj", "'", '"'):
                strs = [a for a in args if a[:1] in (b"<", b"(")]
                if strs:
                    out.append((pi, pos_x, pos_y, cur_size, cur_font, _show(strs[-1], cur)))
            elif op == "TJ":
                text = "".join(_show(a, cur) for a in args if a[:1] in (b"<", b"("))
                if text:
                    out.append((pi, pos_x, pos_y, cur_size, cur_font, text))
    return out


def lines(path):
    """Group runs into rendered lines: one string per line, form feed between pages."""
    out, buf = [], []
    page, prev_y = None, None
    for p, _x, y, _s, _f, text in runs(path):
        if page is not None and (p != page or (prev_y is not None and abs(y - prev_y) > 2.0)):
            out.append("".join(buf))
            buf = []
            if p != page:
                out.append("\f")
        page, prev_y = p, y
        buf.append(text)
    if buf:
        out.append("".join(buf))
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    if "--runs" in argv:
        print(json.dumps(runs(argv[1])))
    elif "--json" in argv:
        print(json.dumps(lines(argv[1])))
    else:
        sys.stdout.write("\n".join(lines(argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
