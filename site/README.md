# site/ — the standard's explanatory pages

Two hand-written HTML pages that explain, to a stranger arriving cold, what an evidence package
is, what it proves, what it does not, and how to use it.

| file | what it is |
|---|---|
| `index.html` | the purpose: what a package is, why the standard exists, the residual it prints, the five mechanisms, what it is not, the name, status |
| `usage.html` | the usage: verifying, verifying without tooling, producing, chain and anchor, the anchor profiles (P1/P2 and the EU qualified seal), long-term validation and the four outcomes it can reach (§9.3.1 MA-84), the limits, where the evidence lives |
| `site.css` | the stylesheet: the design pass applied — tokens, type scale, layout, dark scheme, print |
| `martelage.typ` | the typeset document, **generated** from the two HTML pages by `../tools/html2typst.py` |
| `martelage-0.2.pdf` | the print artifact, compiled from `martelage.typ` by Typst |
| `Makefile` | `make typst`, `make pdf`, `make check` |
| `README.md` | this file |

**Styling.** The pages are plain semantic HTML and stay readable with CSS off. `site.css` holds the
whole design — no framework, no `<style>` block, no `style` attributes, no JavaScript, and no
external request of any kind (no webfonts, no CDN, no `@import`, no `url()`): the site renders fully
with the network off, because a standard about checking things offline should not need a network to
be read. The design is a proposal applied as specified, not a redesign: the five HTML edits it
required are the two `color-scheme` metas, `class="residual"` on the §3.3 blockquote, and the
`div.table-scroll` wrappers that let a table scroll on a narrow screen — two at the design pass,
three now, the third added with the anchor profiles section of `usage.html`. There are
deliberately **no state colours** — a verdict is coloured by nothing on this page, because the
validator's own words are the only thing entitled to assert one, and an unarmed layer must never
read as a pass (§7, §10.4 item 6).

Serving: the pages link to `../spec/MARTELAGE-0.1.md`, `../README.md` and `../LICENSE` rather than
copying anything, which is correct for the repository tree, where the site is read from `site/`.
Validator and vector paths are quoted as repo-relative text, because the site is not served with the
validator next to it.

Publishing: `.github/workflows/pages.yml` builds a staging directory and deploys it with
`actions/deploy-pages` on every push to `main` (and on `workflow_dispatch`); the URL it deploys to is
<https://jmars.github.io/martelage/>. An Actions artifact is used rather than a branch folder
because Pages' branch sources are the repository root or `/docs`, and the site has to stay in
`site/` for `make -C site pdf`. The staging directory holds `index.html`, `usage.html` and
`site.css` at its root, plus the three link targets at the paths the pages name them by —
`spec/MARTELAGE-0.1.md`, `README.md`, `LICENSE` — because the published root *is* the site's
directory, so the siblings the links point at have to sit beside it. One substitution is made in the
staged copy and only there: a browser resolving `../` from the published root climbs out of the
artifact to `https://jmars.github.io/`, so the leading `../` is stripped from the staged HTML and the
repository's own files keep their `../` links. (`site/README.md` is not staged — it is this document,
and at the staging root it would collide with the repository `README.md` the pages link to.) The PDF
is **not** served by Pages: it stays in the repository, and no page links to it, so the published
site offers no PDF.

Content discipline: every factual claim is traceable to `spec/MARTELAGE-0.1.md` or `README.md`, or
is marked MEASURED with the command that produced it. No marketing register, no adoption claims, no
product framing — one implementation is named only where the standard's own informative Annex A
names it.

## The print artifact (`martelage.typ` → `martelage-0.2.pdf`)

The HTML is the source of truth and stays the source of truth. Typst is the *typesetting* path:
`../tools/html2typst.py` reads `index.html` and `usage.html` and emits `martelage.typ`, which Typst
compiles to `martelage-0.2.pdf`. The artifact's name carries the document version, so a version bump
renames it: `tools/html2typst.py` (the title page and the running footer), `tools/checktext.py` (which
pins the footer it strips) and the `Makefile` are the three places to change, and `make check` fails
if they disagree. **The `.typ` is generated — do not hand-edit it.** Edit the prose in
the HTML and rebuild; a hand edit is lost on the next `make typst`. The browser print stylesheet in
`site.css` (`@media print`) is untouched and still serves people who print the HTML: it is the
fallback, not the artifact.

```
make -C site typst   # python3 tools/html2typst.py      -> site/martelage.typ
make -C site pdf     # typst compile martelage.typ martelage-0.2.pdf   (SOURCE_DATE_EPOCH=0)
make -C site check   # python3 tools/checktext.py       -> every HTML text node present in the PDF
```

Geometry, measured rather than assumed: **A4 portrait, 12 mm margins** — a 186 mm shell, with prose
on a 99 mm measure (66 characters) of Libertinus Serif at 10.5 pt, line advance 1.45 × 10.5 pt. The
measure is the same 99 mm the landscape artifact used: the paper orientation changed, the typography
did not. Tables take the 186 mm portrait shell, as `table` is not held to the prose measure on the
web. Code is Noto Sans Mono at 8.5 pt on `#F0EDE4` with a hairline `#D8D4C6` rule. Nothing is
coloured by state.

Pasted output is never re-flowed as though the program had printed it that way. At 8.5 pt the
portrait shell holds 99 characters (180.0 mm inner width); a block whose widest line is longer than
that is set **smaller** — as small as that line needs, but never below a **7 pt legibility floor**,
where the column holds 120 characters. Seven of the fourteen blocks are set smaller: two at 7.79 pt
and one at 7.58 pt, whose widest line fits unbroken at that size, and four at the 7 pt floor. A line
that does not fit even at 7 pt is broken **at a space** and the continuation is marked `↳`, so it is
the marker, not the typesetter, that says a line was broken: eight lines in the document carry one,
no line carries more than one, and every other byte of the block is unchanged. `make check` enforces
that — it compares each block against the HTML byte for byte after undoing the marked breaks, and
reports any other difference as a miss. A block taller than the page breaks across a page boundary
like any other code. Two builds of the same source are byte-identical: `SOURCE_DATE_EPOCH=0` is
pinned in the `Makefile`, so the PDF carries a constant creation date instead of the build second.

**One orientation.** Every page is A4 portrait: the artifact contains no rotated sheet, no landscape
insert, and no block that moves to a wider one. MEASURED on the built PDF — 18 pages, 18 `/MediaBox`
entries, **one distinct value** (`0 0 595.2756 841.8898`), and no `/Rotate` on any page, with
`/Count 18` on the page tree. That is 18 pages against the landscape build's 16 and the
portrait-with-flipped-inserts build's 22: the flip cost six pages over landscape because each insert
broke the page before and after it, and putting code back into the portrait column gives those pages
back. The count has only ever moved with content, never with geometry: 12 pages before the anchor
profiles section of `usage.html` was written out, 15 when the P3 verifier was built, and 18 now that
the revocation inputs (`--ocsp-response`, `--revocation-dir`) and the document-version record (§11.7)
are written out — the page size, the measure and the code sizes are unchanged, and the whole footer
block on every page still reads `MARTELAGE-0.2 — draft 0.2`. The browser print path is a
different path, and is stated plainly rather than matched: `@media print` in `site.css` still asks for
`size: landscape` and `white-space: pre-wrap`, so printing the HTML from a browser gives a landscape
sheet whose pasted lines re-wrap, while the artifact is portrait and marks every break it makes. The
two paths differ on purpose — the HTML print path is the fallback, and the artifact is the one that
does not re-wrap.
