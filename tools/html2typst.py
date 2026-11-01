#!/usr/bin/env python3
"""Generate site/martelage.typ from site/index.html + site/usage.html.

One copy of the prose: the HTML pages stay the source of truth and this converter
transforms their content into a Typst document. Nothing is copied by hand, nothing is
added that is not in the pages (only page furniture: the running footer, the contents
page and the section rules).

    python3 tools/html2typst.py            # writes site/martelage.typ

Determinism: the output is a pure function of the two input files' bytes. No timestamps,
no dictionary-order iteration, no environment reads.

Geometry, measured (see site/README.md for the numbers behind it):
  * A4 landscape, 12 mm margins -> 273 mm shell. The browser print stylesheet makes the
    same choice (@page { size: landscape; margin: 12mm }) and for the same reason: the
    pasted terminal output has lines up to 217 characters, and portrait would force the
    169-character block to 5.2 pt and the 217-character line to 4.05 pt.
  * Prose measure 99 mm = 66 characters of Libertinus Serif at 10.5 pt (measured
    1.4976 mm per character on real prose from these pages).
  * Code 8.5 pt Noto Sans Mono on #F0EDE4 with a hairline #D8D4C6 rule; 1.799 mm per
    character at 8.5 pt, and 267.0 mm of inner width (273 - 2 x 8.5 pt inset and stroke),
    so 146 characters fit with 1% slack. A block whose longest
    line does not fit is shrunk to fit down to a 7 pt floor; below that floor the line is
    split at a space with a '↳' continuation marker rather than silently wrapped.
"""

import html.parser
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "site")
SOURCES = [("index.html", "index"), ("usage.html", "usage")]

# Page geometry, in millimetres. Kept as literals here and as literals in the preamble:
# the converter needs the numbers to decide per-block code sizes, and the preamble needs
# them to set the page.
SHELL_MM = 273.0          # 297 mm - 2 * 12 mm
CODE_INSET_PT = 8.0       # code block horizontal inset
CODE_STROKE_PT = 0.5      # hairline rule, drawn inside the block's own width
FIT_SAFETY = 0.99         # a pasted line must fit with slack: Typst breaks raw lines at
                          # spaces when they are over by even a fraction of a point
MONO_ADVANCE_EM = 0.6     # Noto Sans Mono advance, measured in Typst: 8.5 pt -> 1.79917 mm
PT_MM = 25.4 / 72.0
CODE_SIZE_PT = 8.5
CODE_FLOOR_PT = 7.0
CONTINUATION = "\u21b3"   # ↳: marks a line broken by this converter, not by the program

CODE_INNER_MM = SHELL_MM - 2 * (CODE_INSET_PT + CODE_STROKE_PT) * PT_MM
CODE_LIMIT_MM = CODE_INNER_MM * FIT_SAFETY


def chars_that_fit(size_pt):
    return int(CODE_LIMIT_MM // (MONO_ADVANCE_EM * size_pt * PT_MM))


def fit_size(longest):
    """Point size at which `longest` characters fit one line, capped at 8.5 pt."""
    need = CODE_LIMIT_MM / (MONO_ADVANCE_EM * longest * PT_MM)
    if need >= CODE_SIZE_PT:
        return CODE_SIZE_PT
    # Round down to 0.01 pt so the size never exceeds what was measured as fitting.
    return int(need * 100) / 100.0


def split_long_lines(text):
    """Return (lines, split_at) for a code block: physical lines, and where we broke one.

    A line longer than what 8.5 pt can hold, in a block that would have to drop below the
    7 pt legibility floor, is broken at the last space that fits and the continuation is
    marked with CONTINUATION. Nothing is re-flowed silently: the caller records the break.
    """
    limit = chars_that_fit(CODE_SIZE_PT)
    out, broke = [], []
    for line in text.split("\n"):
        if len(line) <= limit:
            out.append(line)
            continue
        rest = line
        first = True
        while len(rest) > limit:
            cut = rest.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            piece, rest = rest[:cut], rest[cut:].lstrip(" ")
            out.append(piece if first else CONTINUATION + " " + piece)
            first = False
        out.append(rest if first else CONTINUATION + " " + rest)
        broke.append(len(line))
    return out, broke


# ----------------------------------------------------------------- HTML parsing


class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def cls(self):
        return self.attrs.get("class", "")

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)


VOID = {"meta", "link", "br", "img", "hr", "input"}


class Tree(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(path):
    t = Tree()
    with open(path, encoding="utf-8") as fh:
        t.feed(fh.read())
    return t.root


def find(node, tag):
    for c in node.children:
        if isinstance(c, Node):
            if c.tag == tag:
                return c
            got = find(c, tag)
            if got is not None:
                return got
    return None


# ------------------------------------------------------------- Typst emission

SPECIALS = set('\\"#')


def esc(s):
    """Escape a Python string for a Typst string literal."""
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    return "".join(out)


def ts(s):
    return '#text("%s")' % esc(s)


def norm(s):
    return re.sub(r"\s+", " ", s)


def inline(nodes):
    """Markup for a run of inline nodes. Every text leaf goes through a code-mode
    #text("..."), so no prose character is ever interpreted as Typst markup."""
    pieces = []
    for n in nodes:
        if isinstance(n, str):
            s = norm(n)
            if s:
                pieces.append(("text", s))
            continue
        if n.tag == "br":
            pieces.append(("code", "#linebreak()"))
        elif n.tag in ("strong", "b"):
            pieces.append(("code", "#strong[%s]" % inline(n.children)))
        elif n.tag in ("em", "i"):
            pieces.append(("code", "#emph[%s]" % inline(n.children)))
        elif n.tag == "code":
            pieces.append(("code", "#ic(%s)" % '"%s"' % esc(n.text())))
        elif n.tag == "a":
            pieces.append(("code", link(n)))
        elif n.tag == "span":
            pieces.append(("code", inline(n.children)))
        else:
            raise SystemExit("html2typst: unhandled inline element <%s>" % n.tag)

    # Whitespace at the edges of a block belongs to no glyph.
    if pieces and pieces[0][0] == "text":
        pieces[0] = ("text", pieces[0][1].lstrip(" "))
    if pieces and pieces[-1][0] == "text":
        pieces[-1] = ("text", pieces[-1][1].rstrip(" "))
    return "".join(("#text(\"%s\")" % esc(v)) if k == "text" else v for k, v in pieces)


def link(n):
    """A link: the printed text, then the target as text unless the text is already it.

    The web stylesheet prints ' (href)' after every link that is not a fragment. Here the
    target is printed when the link text does not already name it (matched on the href's
    basename), which is the same rule with the redundancy removed.
    """
    href = n.attrs.get("href", "")
    body = inline(n.children)
    shown = n.text()
    base = href.rsplit("/", 1)[-1]
    print_target = base.split("#")[0] not in shown and href not in shown

    if href.startswith("#"):
        dest = "#link(<%s>)" % href[1:]
        print_target = False
    elif href.startswith(("http://", "https://")):
        dest = '#link("%s")' % esc(href)
    elif re.match(r"^[a-z]+\.html#", href):
        dest = "#link(<%s>)" % href.split("#", 1)[1]
    else:
        dest = None

    out = ("%s[%s]" % (dest, body)) if dest else body
    if print_target:
        out += '#text(" (%s)")' % esc(href)
    return out


class Doc:
    def __init__(self):
        self.lines = []
        self.code_blocks = []   # (source, longest, size, split_lengths)

    def add(self, s):
        self.lines.append(s)

    # -- block level ------------------------------------------------------

    def prose(self, body, above="0pt", below="0.9em"):
        self.add("#block(width: measure, above: %s, below: %s)[%s]" % (above, below, body))

    def heading(self, node, level, first=False, label_id=None):
        body = inline(node.children)
        if level == 2 and not first:
            self.add('#block(width: 100%, above: 2.2em, below: 0pt, height: 0pt,'
                     ' stroke: (top: 0.5pt + rule))[]')
        sec = label_id or node.attrs.get("id")
        label = (" <%s>" % sec) if sec else ""
        self.add("#heading(level: %d)[%s]%s" % (level, body, label))

    def list_block(self, node, ordered=False):
        fn = "enum" if ordered else "list"
        items = []
        for c in node.children:
            if isinstance(c, Node) and c.tag == "li":
                items.append("[%s]" % self.li(c))
        self.add("#block(width: measure, above: 0pt, below: 0.9em)["
                 "#%s(%s, indent: 1.2em, spacing: 0.5em)]" % (fn, ", ".join(items)))

    def li(self, node):
        """One list item: inline content up to a nested list, then the nested list."""
        out, group = [], []

        def flush():
            if group:
                body = inline(group)
                if body:
                    out.append(body)
                del group[:]

        for c in node.children:
            if isinstance(c, Node) and c.tag in ("ul", "ol"):
                flush()
                fn = "enum" if c.tag == "ol" else "list"
                sub = ", ".join("[%s]" % self.li(x)
                                for x in c.children if isinstance(x, Node) and x.tag == "li")
                out.append("#block(above: 0.3em)[#%s(%s, indent: 1.2em, spacing: 0.4em)]"
                           % (fn, sub))
            elif isinstance(c, Node) and c.tag == "p":
                flush()
                out.append(inline(c.children))
            else:
                group.append(c)
        flush()
        return "".join(out)

    def quote(self, node):
        body = []
        for c in node.children:
            if isinstance(c, Node) and c.tag == "p":
                body.append("#block(above: 0.45em, below: 0.45em)[%s]" % inline(c.children))
            elif isinstance(c, str) and norm(c).strip():
                body.append("#block(above: 0.45em, below: 0.45em)[%s]" % inline([c]))
        joined = "".join(body)
        if "residual" in node.cls().split():
            self.add("#residual-block[%s]" % joined)
        else:
            self.add("#quote-block[%s]" % joined)

    def code(self, node, source):
        pre = find(node, "code") or node
        text = pre.text()
        lines, broke = split_long_lines(text) if fit_size(
            max((len(l) for l in text.split("\n")), default=0)) < CODE_FLOOR_PT else (
            text.split("\n"), [])
        longest = max((len(l) for l in text.split("\n")), default=0)
        size = fit_size(longest) if not broke else CODE_SIZE_PT
        if size < CODE_FLOOR_PT:
            size = CODE_SIZE_PT
        self.code_blocks.append((source, longest, size, broke))
        self.add('#code-block(size: %.2fpt)[#raw("%s", block: true, lang: "text")]'
                 % (size, esc("\n".join(lines))))

    def table(self, node):
        rows, caption = [], None
        head_rows = 0

        def walk(n):
            nonlocal caption, head_rows
            for c in n.children:
                if isinstance(c, Node):
                    if c.tag == "caption":
                        caption = inline(c.children)
                    elif c.tag == "tr":
                        cells = [x for x in c.children if isinstance(x, Node) and x.tag in ("th", "td")]
                        rows.append(cells)
                    elif c.tag in ("thead", "tbody", "tfoot"):
                        if c.tag == "thead":
                            head_rows = sum(
                                1 for x in c.children if isinstance(x, Node) and x.tag == "tr")
                        walk(c)

        walk(node)
        ncols = max((len(r) for r in rows), default=1)
        if caption:
            self.add('#block(width: 100%%, above: 1.1em, below: 0.35em)['
                     '#text(size: 9.2pt, fill: muted)[%s]]' % caption)
        cells = []
        for i, row in enumerate(rows):
            for cell in row:
                body = inline(cell.children)
                cells.append("#strong[%s]" % body if i < head_rows else body)
            while len(row) < ncols:
                cells.append("")
        head = ""
        if head_rows:
            head = "table.header(%s), " % ", ".join(
                "[%s]" % cells[i * ncols + j]
                for i in range(head_rows) for j in range(ncols))
            cells = cells[head_rows * ncols:]
        # Auto columns would let a long cell widen the table past the shell (measured: the
        # exit-code table reached 388mm on a 273mm shell), so only the leading column is
        # auto and the rest share the remaining width.
        cols = "(auto, %s)" % ", ".join(["1fr"] * (ncols - 1)) if ncols > 1 else "auto"
        self.add("#block(width: 100%%, above: 0.4em, below: 1.1em)[#table(\n"
                 "  columns: %s, align: left + horizon, inset: (x: 6pt, y: 4.5pt),\n"
                 "  stroke: (x, y) => (bottom: 0.5pt + rule),\n"
                 "  %s%s)]" % (cols, head, ", ".join("[%s]" % c for c in cells)))

    def blocks(self, nodes, first_section=False):
        seen_section = False
        for n in nodes:
            if isinstance(n, str):
                if norm(n).strip():
                    self.prose(ts(norm(n)))
                continue
            t = n.tag
            if t in ("header", "main", "footer", "nav", "div", "section", "article"):
                if t == "nav":
                    self.nav(n)
                elif t == "section":
                    kids = n.children
                    for i, c in enumerate(kids):
                        if isinstance(c, Node) and c.tag in ("h2", "h3", "h1"):
                            self.heading(c, {"h1": 1, "h2": 2, "h3": 3}[c.tag],
                                         first=first_section and not seen_section,
                                         label_id=n.attrs.get("id"))
                            seen_section = True
                            rest = [x for x in kids[i + 1:]]
                            self.blocks(rest)
                            break
                    else:
                        self.blocks(kids)
                else:
                    self.blocks(n.children, first_section)
            elif t == "h1":
                self.heading(n, 1)
            elif t == "h2":
                self.heading(n, 2, first=first_section)
            elif t == "h3":
                self.heading(n, 3)
            elif t == "p":
                self.prose(inline(n.children))
            elif t == "ul":
                self.list_block(n)
            elif t == "ol":
                self.list_block(n, ordered=True)
            elif t == "blockquote":
                self.quote(n)
            elif t == "pre":
                self.code(n, "pre")
            elif t == "table":
                self.table(n)
            elif t == "caption":
                pass
            else:
                raise SystemExit("html2typst: unhandled block element <%s>" % t)

    def nav(self, node):
        items = []
        for c in node.children:
            if isinstance(c, Node) and c.tag == "ul":
                for li in c.children:
                    if isinstance(li, Node) and li.tag == "li":
                        items.append("[%s]" % inline(li.children))
        self.add("#block(width: 100%%, stroke: (top: 0.5pt + rule, bottom: 0.5pt + rule),"
                 " inset: (y: 5pt), above: 1.3em, below: 1.3em)["
                 "#block(width: measure)[#list(%s, indent: 1.2em, spacing: 0.45em)]]"
                 % ", ".join(items))


PREAMBLE = r"""// MARTELAGE-0.1 -- typeset print artifact of the standard's explanatory pages.
//
// GENERATED by tools/html2typst.py from site/index.html and site/usage.html.
// DO NOT EDIT: the prose is authored in the HTML only, and the text below is generated
// from it. `make -C site check` verifies this file is still exactly what the converter
// produces, so a hand edit here is caught rather than silently becoming a second copy.
//
// No Typst package is imported (no package specifier appears in this file, so a grep for
// one is a real check) and no external resource is fetched: the document compiles with
// built-in functions and the fonts installed on the host.

#set document(title: "__TITLE__")

// Straight quotes stay straight, and ligatures are off, so a character extracted or
// copied out of the PDF is the character that is in the HTML.
#set smartquote(enabled: false)
#set text(
  font: ("Libertinus Serif", "New Computer Modern"),
  size: 10.5pt,
  fill: rgb("#211E18"),
  lang: "en",
  features: (liga: 0, clig: 0),
)
#set par(justify: false, leading: 0.792em)  // measured: 1.45 x 10.5pt line advance
#set text(hyphenate: false)
#set heading(numbering: none)
#show heading: set text(font: ("Libertinus Serif", "New Computer Modern"))
#show heading: set block(above: 1.1em, below: 0.5em)
// The web's type scale, carried over: 1.75rem / 1.375rem / 1.125rem against a 1rem body.
#show heading.where(level: 1): set text(size: 18.375pt)
#show heading.where(level: 2): set text(size: 14.4375pt)
#show heading.where(level: 3): set text(size: 11.8125pt)

#let ink = rgb("#211E18")
#let muted = rgb("#5B574C")
#let rule = rgb("#D8D4C6")
#let surface = rgb("#F0EDE4")
#let accent = rgb("#8A6A1F")
#let mono = ("Noto Sans Mono", "DejaVu Sans Mono")
// Typst's default raw styling names DejaVu Sans Mono explicitly, so the family has to be
// set on the raw element itself: a surrounding set rule does not reach it.
#show raw: set text(font: mono)

// Prose measure: 66 characters of Libertinus Serif at 10.5pt (measured 1.4976 mm per
// character on this prose). Tables and code take the full 273mm shell, as on the web,
// where pre and table are not held to the prose measure.
#let measure = 99mm

#set page(
  width: 297mm,
  height: 210mm,
  margin: 12mm,
  footer: context {
    set text(size: 8pt, fill: muted)
    block(width: 100%, stroke: (top: 0.5pt + rule), inset: (top: 4pt), above: 0pt, below: 0pt)[
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [MARTELAGE-0.1 \u{2014} draft 0.1],
        [#counter(page).display() / #counter(page).final().first()],
      )
    ]
  },
)

// Typst's default raw styling renders at 0.8em of its surroundings (measured: 10.5pt of
// surrounding text -> 8.4pt of code), so a code size is divided by 0.8 here to make the
// glyphs render at the size named.
#let raw-size(size) = size / 0.8

// Inline code: monospace at 0.875em, no fill (the web sets no background on inline code).
#let ic(body) = box(text(font: mono, size: raw-size(9.1875pt))[#raw(body, block: false)])

// A pasted block: #F0EDE4 fill, hairline rule, fixed line structure. `size` is chosen per
// block by the converter so that no shipped line is wrapped; see site/README.md.
#let code-block(size: 8.5pt, body) = block(
  width: 100%,
  fill: surface,
  stroke: 0.5pt + rule,
  inset: (x: 8pt, y: 6pt),
  radius: 2pt,
  above: 0.9em,
  below: 1.0em,
  text(font: mono, size: raw-size(size), fill: ink, body),
)

// Prose blockquote: the ochre rule, nothing else.
#let quote-block(body) = block(
  width: measure,
  stroke: (left: 3pt + accent),
  inset: (left: 11pt, right: 0pt, top: 2pt, bottom: 2pt),
  above: 0.9em,
  below: 0.9em,
  body,
)

// The section 3.3 residual: surface tint and rule, at body size and body ink. Never
// smaller, never muted, never a footnote.
#let residual-block(body) = block(
  width: measure,
  fill: surface,
  stroke: (
    left: 4pt + accent,
    top: 0.5pt + rule,
    bottom: 0.5pt + rule,
    right: 0.5pt + rule,
  ),
  inset: (x: 12pt, y: 9pt),
  radius: 2pt,
  above: 1.0em,
  below: 1.0em,
  text(size: 10.5pt, fill: ink, body),
)

#outline(title: [Contents], depth: 2)
#pagebreak()
"""


def build():
    docs = []
    titles = []
    for name, _key in SOURCES:
        root = parse(os.path.join(SITE, name))
        title = find(root, "title")
        titles.append(title.text() if title else "")
        docs.append(root)

    d = Doc()
    body = d.lines
    d.add(PREAMBLE.replace("__TITLE__", esc(titles[0])))

    footers = []
    for i, root in enumerate(docs):
        if i:
            d.add("#pagebreak()")
        body_node = find(root, "body")
        for c in body_node.children:
            if isinstance(c, Node) and c.tag == "footer":
                footers.append(c)
                continue
            if isinstance(c, str):
                if norm(c).strip():
                    d.prose(ts(norm(c)))
                continue
            if c.tag == "header":
                # h1, then the intro paragraph(s) and the nav, in document order.
                first_section = True
                d.blocks(c.children, first_section=True)
            elif c.tag == "main":
                d.blocks(c.children, first_section=True)
            else:
                d.blocks([c])

    # The site footer is identical on both pages; emitting it twice in one document would
    # read as a printing fault, so it is emitted once, at the end.
    if footers:
        same = len({f.text() for f in footers}) == 1
        for f in footers[:1]:
            d.add("// site footer: identical on both pages, emitted once at the end")
            d.blocks(f.children)
        if not same:
            raise SystemExit("html2typst: the two footers differ; emit both")

    out = []
    for line in d.lines:
        out.append(line)
    return "\n".join(out) + "\n", d.code_blocks


def main(argv):
    text, blocks = build()
    dest = os.path.join(SITE, "martelage.typ")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    for source, longest, size, broke in blocks:
        note = ""
        if broke:
            note = "; split %s with a continuation marker" % broke
        print("%-6s longest line %3d chars -> %.2fpt%s"
              % (source, longest, size, note))
    print("wrote %s (%d bytes)" % (dest, len(text.encode())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
