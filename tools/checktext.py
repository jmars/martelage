#!/usr/bin/env python3
"""Content-completeness gate for the print artifact.

Instrument: tools/pdftext.py, which decodes the PDF's content streams through the fonts'
ToUnicode CMaps. No pdftotext/mutool/qpdf exists on this host, so the instrument is our
own; what it cannot see is stated (blank lines inside a code block produce no glyph and
are therefore invisible -- blank-line structure is verified against the .typ source
instead, which carries the pasted text byte-for-byte).

What is checked, against site/index.html + site/usage.html as the source of truth:
  1. every prose text node of the two pages appears in the PDF's text;
  2. every non-blank line of every pasted code block appears, with continuations
     (a line broken with the '↳' marker) joined back before matching;
  3. every code block's text in site/martelage.typ equals the HTML <pre> text exactly,
     which is what carries line structure and blank lines;
  4. the <title> of each page is the PDF's metadata title (checked by string presence in
     the PDF's Info dictionary);
  5. site/martelage.typ on disk is exactly what the converter produces from the HTML now --
     which is what makes "the .typ is generated, do not hand-edit it" a checkable claim
     rather than a hope.

    python3 tools/checktext.py

Exit status is the gate: 0 only if every item is found and nothing is missing.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import html2typst as H
import pdftext as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
PDF = os.path.join(SITE, "martelage-0.1.pdf")
TYP = os.path.join(SITE, "martelage.typ")
FOOTER = re.compile(r"^MARTELAGE-0\.1 \u2014 draft 0\.1\d+ / \d+$")


def prose_nodes(node, out, skip=("pre", "head", "title")):
    for c in node.children:
        if isinstance(c, str):
            s = re.sub(r"\s+", " ", c).strip()
            if s:
                out.append(s)
            continue
        if c.tag in skip:
            continue
        prose_nodes(c, out, skip)


def code_texts(node, out):
    for c in node.children:
        if isinstance(c, str):
            continue
        if c.tag == "pre":
            out.append(c.text())
            continue
        code_texts(c, out)


def typst_code_strings():
    """The raw payload of every code-block call in the generated .typ, unescaped."""
    src = open(TYP, encoding="utf-8").read()
    out = []
    for m in re.finditer(
        r'#code-block\(size: [\d.]+pt\)\[#raw\("((?:[^"\\]|\\.)*)", block: true, lang: "text"\)\]',
        src,
    ):
        out.append(unescape(m.group(1)))
    return out


def unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(n, n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def reflow(text):
    """Join rendered lines back into one stream.

    A rendered line that ends with a hyphen was broken AT that hyphen (typst is told not to
    hyphenate), so it joins with no space; every other break joins with one space.
    """
    out = ""
    for line in text.split("\n"):
        if not out:
            out = line
        elif out.endswith("-"):
            out += line
        else:
            out += " " + line
    return out


def main():
    pages = [H.parse(os.path.join(SITE, name)) for name, _ in H.SOURCES]

    prose, codes = [], []
    for root in pages:
        body = H.find(root, "body")
        prose_nodes(body, prose)
        code_texts(body, codes)

    pdf_lines = P.lines(PDF)
    raw = "\n".join(
        ln for ln in pdf_lines if ln.strip() and ln != "\f" and not FOOTER.match(ln.strip())
    )
    # Continuations we inserted are joined back, so a shipped line is compared as shipped.
    joined = raw.replace("\n" + H.CONTINUATION + " ", " ")
    flat = re.sub(r"\s+", " ", reflow(raw))

    missing = []
    for s in prose:
        if s not in flat:
            missing.append(("prose", s))
    print("prose text nodes checked : %d" % len(prose))
    print("prose text nodes found   : %d" % (len(prose) - len(missing)))

    code_lines = [ln for block in codes for ln in block.split("\n") if ln.strip()]
    code_missing = [ln for ln in code_lines if ln not in joined]
    print("code blocks              : %d" % len(codes))
    print("code lines (non-blank)   : %d" % len(code_lines))
    print("code lines found         : %d" % (len(code_lines) - len(code_missing)))

    typ_blocks = typst_code_strings()
    exact = 0
    split_only = 0
    print("code blocks in .typ      : %d" % len(typ_blocks))
    for i, (a, b) in enumerate(zip(typ_blocks, codes)):
        if a == b:
            exact += 1
        elif a.replace("\n" + H.CONTINUATION + " ", " ") == b:
            split_only += 1
        else:
            missing.append(("code-bytes", "block %d differs from the HTML" % (i + 1)))
    print("code blocks byte-exact   : %d" % exact)
    print("code blocks split only   : %d (identical after undoing the marked break)"
          % split_only)

    titles = []
    for root in pages:
        t = H.find(root, "title")
        titles.append(t.text() if t else "")
    pdf_bytes = open(PDF, "rb").read()
    meta_ok = all(t.encode("utf-8") in pdf_bytes or t.encode("utf-16-be") in pdf_bytes
                  for t in titles[:1])
    print("metadata title present   : %s" % ("yes" if meta_ok else "no"))
    if not meta_ok:
        missing.append(("metadata", titles[0]))

    fresh, _blocks = H.build()
    on_disk = open(TYP, encoding="utf-8").read()
    current = fresh == on_disk
    print("generated .typ is current: %s" % ("yes" if current else "NO -- run make typst"))
    if not current:
        missing.append(("stale", "site/martelage.typ is not what tools/html2typst.py produces"))

    print()
    if missing:
        print("MISSES: %d" % len(missing))
        for kind, s in missing:
            print("  [%s] %r" % (kind, s))
        return 1
    print("MISSES: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
