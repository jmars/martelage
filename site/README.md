# site/ — the standard's explanatory pages

Two hand-written HTML pages that explain, to a stranger arriving cold, what an evidence package
is, what it proves, what it does not, and how to use it.

| file | what it is |
|---|---|
| `index.html` | the purpose: what a package is, why the standard exists, the residual it prints, the five mechanisms, what it is not, the name, status |
| `usage.html` | the usage: verifying, verifying without tooling, producing, chain and anchor, the limits, where the evidence lives |
| `site.css` | the stylesheet: the design pass applied — tokens, type scale, layout, dark scheme, print |
| `martelage.typ` | the typeset document, **generated** from the two HTML pages by `../tools/html2typst.py` |
| `martelage-0.1.pdf` | the print artifact, compiled from `martelage.typ` by Typst |
| `Makefile` | `make typst`, `make pdf`, `make check` |
| `README.md` | this file |

**Styling.** The pages are plain semantic HTML and stay readable with CSS off. `site.css` holds the
whole design — no framework, no `<style>` block, no `style` attributes, no JavaScript, and no
external request of any kind (no webfonts, no CDN, no `@import`, no `url()`): the site renders fully
with the network off, because a standard about checking things offline should not need a network to
be read. The design is a proposal applied as specified, not a redesign: the five HTML edits it
required are the two `color-scheme` metas, `class="residual"` on the §3.3 blockquote, and the two
`div.table-scroll` wrappers that let a table scroll on a narrow screen. There are deliberately **no
state colours** — a verdict is coloured by nothing on this page, because the validator's own words
are the only thing entitled to assert one, and an unarmed layer must never read as a pass (§7,
§10.4 item 6).

Serving: the repository is served from its root, so pages link to `../spec/MARTELAGE-0.1.md`,
`../README.md` and `../LICENSE` rather than copying anything. Validator and vector paths are quoted
as repo-relative text, because the site is not served with the validator next to it.

Content discipline: every factual claim is traceable to `spec/MARTELAGE-0.1.md` or `README.md`, or
is marked MEASURED with the command that produced it. No marketing register, no adoption claims, no
product framing — one implementation is named only where the standard's own informative Annex A
names it.

## The print artifact (`martelage.typ` → `martelage-0.1.pdf`)

The HTML is the source of truth and stays the source of truth. Typst is the *typesetting* path:
`../tools/html2typst.py` reads `index.html` and `usage.html` and emits `martelage.typ`, which Typst
compiles to `martelage-0.1.pdf`. **The `.typ` is generated — do not hand-edit it.** Edit the prose in
the HTML and rebuild; a hand edit is lost on the next `make typst`. The browser print stylesheet in
`site.css` (`@media print`) is untouched and still serves people who print the HTML: it is the
fallback, not the artifact.

```
make -C site typst   # python3 tools/html2typst.py      -> site/martelage.typ
make -C site pdf     # typst compile martelage.typ martelage-0.1.pdf   (SOURCE_DATE_EPOCH=0)
make -C site check   # python3 tools/checktext.py       -> every HTML text node present in the PDF
```

Geometry, measured rather than assumed: **A4 landscape, 12 mm margins** — the same page the print
stylesheet asks for, and for the same reason. The pasted terminal output has lines up to 217
characters; at a portrait 186 mm shell the 169-character block would have to be set at 5.2 pt and the
217-character line at 4.05 pt, which is unreadable. Prose is 66 characters (99 mm) of Libertinus
Serif at 10.5 pt, line advance 1.45 × 10.5 pt; tables and code take the full 273 mm shell, as they do
on the web, where `pre` and `table` are not held to the prose measure. Code is Noto Sans Mono at
8.5 pt on `#F0EDE4` with a hairline `#D8D4C6` rule. Nothing is coloured by state.

Pasted output is never re-flowed as though the program had printed it that way. A block whose longest
line does not fit the 267 mm inner width is set smaller (one block: 7.38 pt); a line that would need
to go below 7 pt is broken at a space and the continuation is marked `↳` (one line in the document:
the 217-character `residual` line of the first validator output). Two builds of the same source are
byte-identical: `SOURCE_DATE_EPOCH=0` is pinned in the `Makefile`, so the PDF carries a constant
creation date instead of the build second.
