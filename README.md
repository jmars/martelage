# Martelage — the Evidence Package standard

**Status: draft 0.1.** This repository holds the standard, its reference validator, and the test
vectors that prove the validator can fail. Nothing here is committed to a registry, published by a
standards body, or certified by anyone.

## What this is

An **evidence package** is a directory of hash-chained record files plus one manifest that states its
own scope, its place in a package chain, and whether anyone other than the operator holds its
digest — checkable offline by anyone with a POSIX shell and `sha256sum`, against a validator that
prints what it cannot check on every run.

The point of the format is the sentence it refuses to overclaim: *a package proves that what it
contains was not altered after it left; it cannot prove that what it contains is all there was, and
against an operator who rewrote everything before the first anchor it proves nothing.* Every
mechanism in the standard is specified separately, with what it buys and what it does not, so that a
reader cannot credit the weakest layer with the strength of the strongest.

| file | what it is |
|---|---|
| `spec/MARTELAGE-0.1.md` | the standard. Every normative requirement carries an identifier (`MA-1` … `MA-82`) so a conformance report can cite it. |
| `validator/martelage-verify` | the reference validator: POSIX shell + the set §10.1 names (`awk`, `sed`, `grep`, `cmp`, `sort`, `sha256sum`, `tr`, `cut`, `head`, `tail`, `wc`, `find`, `mktemp`, `rm`, `cat`). No network, no interpreter beyond those, no keys, no service, no producer. |
| `vectors/` | thirty-three hand-made packages with their expected results. Constructed for the standard; none is exported from a producer system. |
| `LICENSE` | the licence split: specification text CC BY 4.0, code Apache-2.0. |

The standard is published on its own. It defines concepts — a record envelope, a stream, a package
manifest, a scope statement, an anchor statement — and one generic JSON binding for them. No
normative clause names a particular implementation's file, path, tool or field spelling. Annex A is
the one place a specific system is named, and it is informative.

## Running the validator

```sh
sh validator/martelage-verify vectors/01-minimal-conformant/pkg        # exit 0
sh validator/martelage-verify --help
```

Exit codes are the gate, not the tail of the output:

| code | meaning |
|---|---|
| `0` | **CONFORMANT** — every check the run could perform passed. An unanchored package exits 0; the NOT-ANCHORED line has been printed. |
| `1` | **NON-CONFORMANT** — a check failed. |
| `2` | **USAGE OR UNREADABLE** — bad invocation, or an input that could not be read. |
| `3` | **CANNOT DECIDE** — an input the validator needs to decide is absent (anchor evidence, trust anchors, a profile-specific verifier). It names the missing input. |

Code 3 exists because an instrument that cannot return "undecided" returns something else instead.

## The vectors, with expected and actual results

Every row below was run on the tree as shipped. `expected.txt` in each vector directory records the
same thing, plus the requirement identifiers the case exercises.

| # | vector | what it exercises | expected | actual |
|---|---|---|---|---|
| 01 | `01-minimal-conformant` | a conformant package; NOT ANCHORED printed; layer 3 reported unarmed | 0 | **0** |
| 02 | `02-broken-predecessor` | one record's `prev` names nothing in its stream | 1 | **1** |
| 03 | `03-stream-gap` | seq 1, 2, 4 — an interior record removed | 1 | **1** |
| 04 | `04-anchor-unverifiable` | a claimed p1 anchor with no evidence supplied | 3 | **3** |
| 05 | `05-anchored-verified` | the same package with the holder's digest supplied | 0 | **0** |
| 05b | `05` without `--anchor-evidence` | the same claim, unarmed | 3 | **3** |
| 06 | `06-payload-digest-mismatch` | `files[0].sha256` does not match the bytes | 1 | **1** |
| 07 | `07-scope-vocabulary` | a scope meaning word outside the vocabulary | 1 | **1** |
| 08 | `08-two-writers` | two writers, two files, never merged; a disagreement between them is a finding | 0 + 1 finding | **0 + 1 finding** |
| 09 | `09-torn-tail` | a final line with no terminating newline | 1 | **1** |
| 10 | `10-chain` + `--prev-package pkg-1` | a package that extends its predecessor | 0 | **0** |
| 10b | `10` without `--prev-package` | the same package, chain unarmed | 0 | **0** |
| 11 | `11-chain-omission` + `--prev-package pkg-1` | a record dropped across packages | 1 | **1** |
| 11b | `11` without `--prev-package` | the omission, unarmed — invisible | 0 | **0** |
| 12 | `12-seam-findings` | two files disagreeing about one stream, and a backwards timestamp | 0 + 2 findings | **0 + 2 findings** |
| 13 | `13-chain-subdir` + `--prev-package pkg-1` | the predecessor keeps its records one directory down and the successor drops that stream | 1 | **1** |
| 13b | `13` without `--prev-package` | the same omission, chain unarmed — invisible | 0 | **0** |
| 14 | `14-manifest-whitespace` | `"v": 1` — one space between tokens | 1 | **1** |
| 15 | `15-manifest-duplicate-key` | the same key twice in one object | 1 | **1** |
| 16 | `16-nul-in-record` | a NUL byte inside a record body, every digest correct | 1 | **1** |
| 17 | `17-bad-writer` | `writer` outside its charset (`exa mple`) | 1 | **1** |
| 18 | `18-bad-stream-name` | `stream` outside its charset (`no te`) | 1 | **1** |
| 19 | `19-subject-path` | `subject.id` shaped like a filesystem path | 1 | **1** |
| 20 | `20-created-at-zero` | `created_at` rendered as `0` for absent | 1 | **1** |
| 21 | `21-record-ts-zero` | a record `ts` of `0` | 1 | **1** |
| 22 | `22-claim-when-unanchored` | `anchored:false` carrying a claim object | 1 | **1** |
| 23 | `23-claim-carries-digest` + `--anchor-evidence` | a claim value that is a bare 64-hex digest | 1 | **1** |
| 23b | `23` without `--anchor-evidence` | the same package: refused, and undecided as well | 1 | **1** |
| 24 | `24-duplicate-file-entry` | one file listed twice in `files[]` | 1 | **1** |
| 25 | `25-unknown-fields` | two keys this standard does not define | 0 | **0** |
| 26 | `26-kind-not-stream` | `kind` "other" on a stream named `note` — §6.2 makes them equal at payload contract v1 | 1 | **1** |
| 27 | `27-phantom-stream` | line 1 declares a stream `n:5` with a head, and no record is on it | 1 | **1** |
| 27b | `27` with the legitimate empty declaration | `n:0`, head `null`, and `counts.streams` counting it | 0 | **0** |
| 28 | `28-p2-contradicted-evidence` + wrong `--anchor-evidence` | a p2 claim whose evidence states a different digest | 1 | **1** |
| 28b | `28` + matching evidence | the digest matches; inclusion is still not checkable | 3 | **3** |
| 29 | `29-symlink` | an unlisted symlink pointing out of the package | 1 | **1** |
| 29b | `29` with the link listed | a listed symlink whose digest was computed through the link | 1 | **1** |
| 30 | `30-residual-on-usage-error` | the residual on an exit-2 usage error that names a package | 2 | **2** |
| 31 | `31-role-not-a-word` | a `files[]` `role` of `DOCUMENT!!` — §5.2.6 says a lowercase word | 1 | **1** |
| 31b | `31` with the role `human-notes` | a role this standard does not define, but a lowercase word: carried, hashed, never parsed | 0 | **0** |
| 32 | `32-seam-writers` | two writers over ONE body at seq 1 — the finding must name both writers and the sequence | 0 + 1 finding | **0 + 1 finding** |
| 32b | `32` `pkg-longer` | the same body at a different seq: the finding names seq 2 and which file holds no record there | 0 + 1 finding | **0 + 1 finding** |
| 33 | `33-scope-printed` | the scope section printed in full, every `not_contains` entry with its meaning word | 0 | **0** |

11b is the residual of §7.4.3 in one line: without the predecessor, a dropped record is invisible,
and the validator says the layer was not armed rather than implying a pass.

Vectors 13–25 were added after a review of this repository found requirements the text specified and
the reference validator did not enforce. Each one is a package built to trip exactly one of those
checks, and each has a mutant of the validator that removes exactly that check and shows the vector
going to the wrong verdict — see "each new check has a mutant" below. A check with no vector and no
mutant is a claim, not a check.

Vectors 26–30 close a second review. Four of them enforce text that was already normative (§6.2
`kind`/`stream`, §6.4/§7.2.1 a declared stream with no records, §9.3/§10.3 a contradicted p2 anchor,
§4.4 an unlisted or listed symlink); the fifth covers §3.3: the residual must be printed on a run
that names a package even when the run ends at exit 2 for a usage error. The symlink rule was not in
the text at all, so it was added as **MA-82** — the next free identifier, nothing renumbered. Each of
the five has a mutant row below, and each vector's `expected.txt` states why it fails without its fix.

Vectors 31–33 close a third pass. 31 enforces a charset the text already stated (§5.2.6 `role` is "a
lowercase word") and no check applied; 32 carries the writer and the real sequence into the seam
finding, which §6.7 (MA-40) requires and which the body_sha-only comparison withheld — it printed
`at seq ?` and named neither writer; 33 asserts a print that MA-59 requires and nothing tested, after
MA-59 was corrected to state only what a validator can do (§8.6 makes the scope's truth
uncheckable, so the old wording described a membership check that no implementation has or should
have). No identifier was added or renumbered: MA-1 … MA-82 are the same set as before.

The same pass examined a fourth candidate and closed it without a check: one file declaring a stream
`n:0` while another file carries records on it. §6.4 scopes `n` and `head` to the records *in that
file*, so the two declarations are independent statements and cannot contradict each other — and a
check requiring them to agree would be §6.7 read backwards, since the seam rule forbids reading two
files as one stream at all. One sentence in §6.4 now says so, because the misreading is what
produced the candidate. The per-file half is a real check and was already armed: a file declaring
`n:0` while carrying records is refused (vector 27).

## The validator can fail — a mutation of itself

A standard whose only validator has never rejected anything is a description of its author's output.
So: remove the predecessor-chain check from a copy of the validator, and vector 02 must stop being
caught.

```
$ cp validator/martelage-verify /tmp/martelage-verify-noprev
# delete the one line that compares a record's prev to its predecessor's body_sha
$ sh validator/martelage-verify vectors/02-broken-predecessor/pkg
refusals
  payload: records.jsonl stream 'note': prev at seq 2 does not name seq 1;
verdict      NON-CONFORMANT
exit=1

$ sh /tmp/martelage-verify-noprev vectors/02-broken-predecessor/pkg
refusals
  none
verdict      CONFORMANT
exit=0
```

`1` → `0` on the broken package, and the mutant still reports `0` on `01-minimal-conformant` — the
mutation removes that check and nothing else. Vector 02 was built for exactly this: seq, count, head
and every digest are consistent, so the `prev` comparison is the only check that can catch it.

### Each new check has a mutant

Same method, one mutant per check added by the review: remove exactly the lines that implement the
check, leave the rest of the validator alone (`sh -n` clean), and run the vector built for it. A
check whose removal changes nothing is not load-bearing.

| check removed from a copy of the validator | vector | fixed | mutant |
|---|---|---|---|
| the undecided block is printed | 04 | names the missing input | **silent (still exit 3)** |
| the predecessor's records come from its manifest | 13 | 1 | **0** |
| no whitespace outside a string value | 14 | 1 | **0** |
| no duplicate key | 15 | 1 | **0** |
| NUL/control bytes refused in a record stream file | 16 | 1 | **0** |
| the whole `writer` charset | 17 | 1 | **0** |
| the whole `stream` charset | 18 | 1 | **0** |
| `subject.id` path shape | 19 | 1 | **0** |
| `created_at` is not `0` | 20 | 1 | **0** |
| a record `ts` is not `0` | 21 | 1 | **0** |
| ignored fields are counted and reported | 25 | names `x-custom` | **silent** |
| `claim` is null when `anchored` is false | 22 | 1 | **0** |
| a claim value may not be a bare digest | 23 | 1 | **0** |
| a file appears exactly once in `files[]` | 24 | 1 | **0** |
| the residual on an exit-2 usage error that names a package | 30 | residual printed | **silent (still exit 2)** |
| `kind` equals `stream` at payload contract v1 | 26 | 1 | **0** |
| a declared stream must be the stream the records are on | 27 | 1 | **0** |
| the p2 evidence digest is compared to the package digest | 28 | 1 | **3** |
| symlinks are enumerated and a listed symlink is refused | 29 | 1 | **0** (both arms) |
| the `role` charset | 31 | 1 | **0** |
| the seam finding names the writer and the real sequence | 32 | names both writers at seq 1 | **`at seq ?`, no writer named (still exit 0)** |
| the scope section is printed in full | 33 | every entry with its meaning word | **silent (still exit 0)** |

Two of these are the difference between a report that names what it could not check and one that does
not: the first row is vector 04's own "must print" line, and vector 23b shows the harder case — a
package that is refused *and* undecided reports exit 1, and still names the input it could not
check, because a refusal must not make an undecided check invisible (MA-71).

## The validator runs on a second shell and a second awk

The whole vector suite above was re-run under `busybox sh` with `busybox awk`, `sed`, `grep`, `cmp`
and `sha256sum` — a different shell and a different awk implementation from the ones used for the
table. All 44 invocations (33 vector runs plus the 11 documented second arms) return the same exit
code, and 43 of 44 produce byte-identical stdout and stderr. The exception is measured and named:
vector 16, a NUL byte inside a record body, is refused by both awks (exit 1) with different refusal
text, because `busybox awk` and `gawk` split a NUL-bearing line differently. That is a difference
between two awks' handling of a byte no conformant package may carry, not a difference in the
verdict. That is what "POSIX shell and coreutils" is supposed to mean, so it was measured rather than
asserted.

## A producer that shares no code with the validator

Annex E of the standard is a worked package written by hand with `printf` and `sha256sum` — two
files, no tooling. Executing that example verbatim, in an empty directory, with nothing from this
repository on the path except the validator itself, produces a package the validator reports
`CONFORMANT` (exit 0). That is the closest thing to a stranger's producer available here: a producer
that shares no code with the checker, written from the document alone.

**What is not here, and why.** A package exported by a *different project's* producer would be a
stronger check, and it is absent: the system this standard's Annex A describes has no store and no
export binary on this host, so a real export could not be manufactured. The payload grammar of the
vectors is the grammar that emitter writes — verified against its source, not against a run — but
that is a reading of a document, not a measurement of a package, and it is marked as such in Annex A.

## What "draft 0.1" means here

- The normative requirements are complete enough to implement against and to cite: the validator in
  this repository is one implementation of them, and the vectors are its evidence.
- The change policy of §11 applies to the **wire format** it defines (`"v":1`) from now on. A change
  to this *document's* requirements may still be breaking while it is a draft; a change to a
  published `v` must not be.
- A conformance statement must name both the document version and the wire version it was made
  against. Annex C is the template; the statement is a claim under the claimant's own name.

## Raising a defect

Open an issue against the sentence, not the code: quote the `MA-` identifier and the text, and say
what it lets a producer or a verifier claim that the format cannot deliver. A defect report that
shows a mechanism implying more than it buys is the most valuable kind, because that is the failure
mode this standard exists to prevent.
