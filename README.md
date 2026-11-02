# Martelage — the Evidence Package standard

**Status: draft 0.1.** This repository holds the standard, its reference validator, and the test
vectors that prove the validator can fail. Nothing here is committed to a registry, published by a
standards body, or certified by anyone.

**The site:** `site/` — the explanatory pages — deploys to GitHub Pages at
<https://jmars.github.io/martelage/> via [`.github/workflows/pages.yml`](.github/workflows/pages.yml)
on every push to `main`. The published pages are that directory; the specification, this README and
`LICENSE` are staged beside them, and are served as files rather than rendered pages.

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
| `validator/p3-verify` | the P3 profile verifier (§9.3 `p3-eidas-qualified-seal-asic-e`): python3 and the `openssl` binary, no third-party library and no network path. Verifies an ASiC-E container's CAdES seal (the detached manifest-signature construction, checked as the construction before anything else is accused), **every signer of every signature entry** and the whole chain each one reaches, the digests it covers, an RFC 3161 token with the TSA's own chain, and revocation **only against CRLs you hand it** with `--revocation` — and prints what it cannot check on every run. A second implementation: `martelage-verify` keeps its zero-dependency property untouched. |
| `tools/` | `mkpki.sh` (the throwaway test PKI), `mkcrl.sh` (the CRLs the revocation vectors hand the verifier), `mkasic.py` (the ASiC-E container builder), `mkp3.sh` (rebuilds the P3 vectors), and the two scripts that render the site's print artifact. |
| `vectors/` | fifty-two hand-made packages and their fixtures, with their expected results. Constructed for the standard; none is exported from a producer system. |
| `LICENSE` | the licence split: specification text CC BY 4.0, code Apache-2.0. |

The standard is published on its own. It defines concepts — a record envelope, a stream, a package
manifest, a scope statement, an anchor statement — and one generic JSON binding for them. No
normative clause names a particular implementation's file, path, tool or field spelling. Annex A is
the one place a specific system is named, and it is informative.

## Anchor profiles

The anchor slot names one of three profiles at this version (§9.3), and the wire string is what a
validator matches: `p1-second-party-digest` — a digest of the package held by an identified party
other than the operator, which the base validator verifies fully; `p2-append-only-log` — an entry in a
ledger held by someone else, whose stated digest the base validator compares to the package digest, a
match still leaving inclusion undecided, so it reports exit 3; and
`p3-eidas-qualified-seal-asic-e` — an ETSI EN 319 162-1 ASiC-E container holding the package files
with a CAdES or XAdES signature by a legal person other than the operator, with a qualified electronic
time stamp and optional long-term validation. **P3 is built, and it is not the base validator that
builds it:** the base validator cannot verify a signature — that needs a signature verifier and trust
anchors, which §9.1(b) keeps out of the base tier — so it still stops at exit code 3 and names the
profile-specific verifier it is not. That verifier is [`validator/p3-verify`](validator/p3-verify),
which verifies the seal and prints what it cannot check (see [The P3 verifier](#the-p3-verifier)
below). No eIDAS certification is claimed for it and no compliance with ETSI EN 319 162-1 is claimed
for it. §9.3 requires three limits to be stated wherever P3 is offered; [the anchor profiles section
of the site](site/usage.html#anchors) states them in full, the first being that a seal made with the
operator's own key is worthless against the operator, because they hold the key.

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

## The P3 verifier

`validator/p3-verify` is the profile-specific verifier §9.3 says a P3 claim needs. It is a **second
implementation**: it shares no code with `martelage-verify`, which is unchanged, and it runs under
`python3` and shells out to the `openssl` binary for every cryptographic operation — python's standard
library has no CMS or X.509 implementation, and there is no third-party crypto library on this host.
It has no network path at all: nothing is downloaded, no URL is opened, and no OCSP responder is
contacted. Revocation is checked only against CRLs the person running it **hands it** with
`--revocation`, and without that option revocation is not checked and the report says so.

```sh
validator/p3-verify \
  --container vectors/34-seal-verified/seal.asice \
  --trust-anchors vectors/pki/anchors \
  --operator-cert vectors/pki/operator.crt.pem \
  vectors/34-seal-verified/pkg                      # exit 0
```

| input | what arming it buys (§10.2 MA-69) |
|---|---|
| `PACKAGE-DIR` | the package the seal claims to bind. It must claim the P3 profile; handed a package that claims another profile, the tool says so and exits 2 |
| `--container FILE` | the ASiC-E container — the evidence itself. Without it the seal is CANNOT DECIDE, not refused |
| `--trust-anchors DIR` | a directory of PEM anchors: what the signer's chain is checked against |
| `--operator-cert FILE` | the operator's own certificate, so that "a legal person OTHER than the operator" (§9.3 limit i) is *checked* rather than assumed — over **every** signer of every signature entry, because the operator only has to be one of them. Without it that clause is CANNOT DECIDE: this verifier never assumes the signer is someone else |
| `--revocation FILE` | a CRL — PEM or DER — to check revocation against, **offline**: the material is an input you supply, and this tool never fetches one. Repeatable, because a chain with more than one issuing CA needs one CRL per CA. With it, every certificate in the established chain that a supplied CRL speaks for is checked, a listed certificate refuses the container, and a certificate no supplied CRL speaks for leaves the run undecidable rather than counted as unrevoked. Without it, revocation is NOT checked. **CRL only**: OCSP is not implemented here at all, not even from a supplied OCSP response |
| `--require-timestamp` | refuse a container that carries no RFC 3161 token |

Exit codes are the same four the standard defines (§10.3 MA-70), with P3's meanings:

| code | meaning |
|---|---|
| `0` | **CONFORMANT** — the container is well-formed (no duplicate entry name, every covered path inside the package), the CAdES signature verifies over the ASiC manifest, every signer of every signature entry chains to a supplied anchor and none is a CA, every sealed digest is the package's, the token verified, every certificate the run established (every signer, the whole chain, the TSA's chain) was valid at the claimed time, and no signer's key is the operator's |
| `1` | **NON-CONFORMANT** — a malformed container (a wrong `mimetype`, a duplicate ZIP entry name, a covered path that leaves the package, a signature entry whose content is **embedded** rather than detached over the manifest), a sealed digest that moved, a signature that does not verify, a signer that is a CA, any signer or chain certificate that was not valid at the claimed time, a token from a TSA that was not, a seal made with the operator's own key **or co-signed with it**, a certificate a supplied CRL lists as revoked, or `--require-timestamp` given with no token |
| `2` | **USAGE OR UNREADABLE** — a bad invocation, an unreadable input, or a package that does not claim P3 |
| `3` | **CANNOT DECIDE** — an input was not supplied or cannot be used: the container, trust anchors, `--operator-cert`, a verified timestamp to establish the claimed time, or revocation material that is expired, not yet valid, of unverifiable signature, or that speaks for only part of the chain |

**What it verifies**, in the order it verifies it: first the **construction** — one construction is
implemented, a detached CAdES over the exact bytes of `META-INF/manifest.xml`, and a signature entry
whose CMS carries its content **embedded** (what `openssl cms -sign ... -nodetach` writes) is refused
by name before anything else is accused, so a container is never reported as a detached signature it
is not. The refusal says so and says that ETSI EN 319 162-1's multi-file concatenated-digest form and
XAdES are equally not implemented here. Then: that the ZIP is an ASiC-E (a correct `mimetype`
present, first and stored; an ASiC manifest under `META-INF/`; a `META-INF/signatures*.p7s`) and that
**no entry name appears twice** — a duplicate name makes the container's content depend on which
reader opens it, so the coverage claim cannot be true for that name; that every entry the manifest
lists is present with the digest it states, that **every covered path stays inside the package** (no
absolute path, no `..`, nothing that resolves out), and that no entry sits outside the manifest's
coverage while claiming to be evidence; that the CAdES signature verifies over the exact bytes of
`META-INF/manifest.xml` (`openssl cms -verify`, DER, `-binary`) and that **every signer of every
signature entry** chains to a supplied anchor — the signer set is enumerated from openssl's `-signer`
output and held against the entry's own signerInfo count, so a co-signer cannot go unchecked; that no
signer is a **CA** (a certificate with `basicConstraints CA:TRUE` is refused as a sealing party); that
every digest the seal covers is the digest of the package file as it is on disk; that an RFC 3161
token, if present, verifies over one of the signature values (`openssl ts -verify`) and that the time
it establishes is the time **every certificate date is checked against** — every signer, every
certificate in the chain each signer reaches, and the timestamping authority's own chain, at the
token's genTime and never at this host's clock; that **no** signer's public key is the
operator's; and, **when `--revocation` is given**, that every supplied CRL is a CRL (PEM or DER), that
its own signature verifies under a certificate this run holds, that its window is current, and that no
certificate in the established chain it speaks for is listed on it — a listed certificate refuses the
container, naming the certificate, the CRL, the revocation date and the reason. Nothing is fetched, at
any point: the CRLs are files the verifier was handed.

**What it does not check, on any run.** Every run prints a section headed `not checkable by this
verifier (every run)` before its verdict, in the state the run is actually in: revocation (unarmed,
the entry says no CRL is read and no OCSP responder is contacted — there is no network path in the
tool, so "valid at the claimed time" means the certificate dates and never revocation status; armed, it
says exactly which CRLs were used, with their issuer, `thisUpdate`, `nextUpdate` and entry count, and
that a certificate no supplied CRL speaks for has no revocation status here, that a revocation
published after a CRL's `nextUpdate` is invisible, and that long-term validation is still never
validated); long-term validation (LTV material is reported present or absent
and is never validated); the truth and completeness of the records (§9.3 limit iii); the signer's legal
identity beyond the subject its certificate claims; whether the certificate was issued for sealing at
all (this standard defines no key-usage profile for a seal, so the chain is verified with `-purpose
any`, and that is stated rather than assumed — the CA bit is the one key-usage-shaped property that
*is* checked, because a CA is not a sealing party); and a re-forged history (§9.3 limit ii). The block
is printed on exit-2 runs too, to stderr, so "on every run" is true of the runs that have no report as
well. A run that could not check something never reads as having checked it, and a check it did not
arm is printed as unarmed rather than as a pass (§10.4 item 6, MA-71).

**What this is not.** Not a qualified trust service, not an eIDAS certification, and not a claim of
compliance with ETSI EN 319 162-1. The container shape it verifies is the manifest-signature form — a
detached CAdES over `META-INF/manifest.xml`, carrying the covered files' digests in that manifest —
and the tool says so in its own report, because the EN 319 162-1 multi-file concatenated-digest form
is not what it parses and it will not report that as verified. A container of another shape is
**refused**, not absorbed: an embedded-content CMS, the concatenated-digest form and XAdES are all
shapes this verifier does not implement, and a run that met one says which shape it met. Not a
revocation service either: `--revocation` checks the CRLs it is handed and nothing else, and there is
no live OCSP, no CRL download and no long-term-validation checking anywhere in the tool. It does not
make `martelage-verify` verify seals, and a P3 claim handed to the base validator still reports exit 3.

### The P3 fixtures, and how to rebuild them

`vectors/pki/` is a **throwaway** test PKI: two roots, an intermediate, a sealer (`CN=Witness AG`), a
second sealer under the root the vectors withhold, a sealer whose certificate expired in 2021, a
second sealer under the same intermediate as the first (the two-signer control), an intermediate and a
TSA certificate with the same keys and subjects as the valid ones but expired in 2021, the operator
(`CN=Operator GmbH`) and a timestamping authority. **The private keys are committed on
purpose** — a vector that cannot be rebuilt from what is in the tree is not reproducible — and they
are worth exactly nothing; see [`vectors/pki/README.md`](vectors/pki/README.md). Validity dates are
fixed with `-not_before`/`-not_after`, so the expired-signer vector is expired on any host at any time;
key material is regenerated on every run, so regenerating the PKI means rebuilding the containers:

```sh
sh tools/mkpki.sh      # the test PKI: new keys, the same dates and layout, then the CRLs
sh tools/mkcrl.sh      # just the CRLs, from the certificates already in vectors/pki
sh tools/mkp3.sh       # vectors 34..52: the packages and their containers
```

All three run offline and need only `openssl` and `python3`. `tools/mkcrl.sh` writes the CRLs the
revocation vectors hand the verifier — one per CA in the chain, plus a revoked entry, an expired
window and a CRL from a CA that issued nothing in the chain, each with its dates fixed for the same
reason the certificate dates are. `tools/mkasic.py` is the container builder, and its docstring
states the container shape it produces; `--embedded-content` builds the shape it does **not** produce
(`-nodetach`), which is what vector 48 refuses.

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
| 34 | `34-seal-verified` | a P3 seal that verifies fully, with a checked RFC 3161 token, a supplied anchor and the operator's certificate | 0 | **0** |
| 34b | `34` without `--operator-cert` | the same container: the "legal person other than the operator" clause is undecided, not assumed | 3 | **3** |
| 34c | `34` through the base validator | the base validator stops at the profile it is not | 3 | **3** |
| 35 | `35-seal-digest-moved` | a valid seal over a package that moved under it — `pkg-moved` is internally consistent | 1 | **1** |
| 35b | `35` against the sealed package | the same container, the package it was made over | 0 | **0** |
| 36 | `36-anchor-untrusted` | the seal chains to no supplied anchor: CANNOT DECIDE, not a refusal | 3 | **3** |
| 36b | `36` with `--trust-anchors vectors/pki/anchors-b` | the same container with root B supplied | 0 | **0** |
| 37 | `37-self-seal` | the operator sealed with its own key — §9.3 limit (i) | 1 | **1** |
| 37b | `37` without `--operator-cert` | the same container: the clause is undecided | 3 | **3** |
| 38 | `38-no-timestamp` + `--require-timestamp` | a container with no token, refused because the run required one | 1 | **1** |
| 38b | `38` without `--require-timestamp` | nothing refused; no verified time, so the date check is unreachable | 3 | **3** |
| 39 | `39-container-malformed` `seal-bad-mimetype` | a `mimetype` of `application/zip` | 1 | **1** |
| 39b | `39` `seal-missing-entry` | the ASiC manifest lists an entry the ZIP does not hold | 1 | **1** |
| 40 | `40-signer-expired` | the signer's certificate expired in 2021, at a claimed time of now | 1 | **1** |
| 41 | `41-signature-broken` | the ASiC manifest altered after signing, every stated digest intact | 1 | **1** |
| 41b | `41`'s container before the manifest was touched | vector 34's container | 0 | **0** |
| 42 | `42-multisigner-operator` | the operator's key as a SECOND signer behind a valid signer — §9.3 limit (i) with the operator one certificate further along | 1 | **1** |
| 42b | `42` `seal-two-signers.asice` | the same two-signer construction with a second sealer, no operator | 0 | **0** |
| 43 | `43-ca-signer` | a CA certificate (`basicConstraints CA:TRUE`) used as the sealing party | 1 | **1** |
| 44 | `44-chain-expired` | the signer is valid and the intermediate it chains through expired in 2021 | 1 | **1** |
| 45 | `45-tsa-expired` | a token from a TSA certificate that expired in 2021 | 1 | **1** |
| 46 | `46-zip-duplicate` | two ZIP entries named `notes.md`; the covered digest is the last one's, the shadowed bytes are the first one's | 1 | **1** |
| 47 | `47-manifest-path-escape` | the ASiC manifest covers `../outside.txt`, a file beside the package | 1 | **1** |
| 48 | `48-embedded-content` | the signature entry's content is EMBEDDED (`-nodetach`), not detached over the manifest: a shape this verifier does not implement | 0 | **1** |
| 48b | `48` `seal-detached.asice` | the same build without `-nodetach` | 0 | **0** |
| 49 | `49-revocation-revoked` | the sealer's serial is on the CRL handed in with `--revocation` | **2** | **1** |
| 49b | `49` with the same CAs' clean CRLs | one entry removed from the CRL, nothing else | **2** | **0** |
| 50 | `50-revocation-clean` | every chain certificate is spoken for and none is listed | **2** | **0** |
| 50b | `50` with intermediate A's CRL in DER form | the same bytes in the other encoding | **2** | **0** |
| 51 | `51-revocation-wrong-issuer` | a valid CRL from a CA that issued nothing in this chain | **2** | **3** |
| 52 | `52-revocation-expired` | a CRL whose `nextUpdate` is in 2021: unusable, never a pass | **2** | **3** |

11b is the residual of §7.4.3 in one line: without the predecessor, a dropped record is invisible,
and the validator says the layer was not armed rather than implying a pass.

Rows 34–52 are the P3 vectors, and they are the first ones run against `validator/p3-verify` rather
than `martelage-verify`. Each pair is built so that the two arms differ by exactly one thing — the
container, the anchor directory, one flag, one key, one byte, one CRL entry — so the exit code is
decided by the check under test and by nothing else. Row 35 is the one that shows what the profile
buys: the sealed package and `pkg-moved` are both internally consistent, both report no refusal from
the base validator, and only the seal can tell them apart.

Rows 48–52 close two of the owner's own items. **48** is the shape: the same container built with
`openssl cms -sign ... -nodetach`, whose signature carries its content embedded instead of leaving it
detached over the manifest. Before the fix that container reported exit **0** while the report
asserted "`CAdES, detached, DER`" and "construction detached CAdES over the exact bytes of
`META-INF/manifest.xml`" — two statements about a construction the run never read. It is now refused
by name, and the refusal says that the EN 319 162-1 concatenated-digest form and XAdES are equally
not implemented. **49–52** are `--revocation`: the sealer is on a CRL the verifier is handed; the
same container with a CRL that lists nobody; a valid CRL from a CA that issued nothing in the chain;
and a CRL whose window ended in 2021. The four arms differ only in the revocation material, and
between them they pin the three states a revocation input can be in: **refused**, **checked clean**,
and **not checkable** — the last of which must never be printed as either of the other two. Rows
49–52 have a **2** in the "before" column on purpose: the option they exercise did not exist, so the
invocation ended at exit 2 ("unknown option `--revocation`") and the verifier could not be handed
revocation material at all. What those rows measure is the check the option buys, not a change of
heart about a verdict that already existed.

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

### The P3 checks have mutants too

Same method against `validator/p3-verify`: copy it, remove exactly the check under test, run the
vector built for it, and confirm the mutant still passes vector 34 — the arm where every check is
armed and every check passes. Measured on this tree:

| check removed from a copy of `p3-verify` | vector | fixed | mutant | control (34) |
|---|---|---|---|---|
| the sealed digest is compared to the package on disk | 35 | 1 | **0** | 0 |
| the signer's key is compared to `--operator-cert` | 37 | 1 | **0** | 0 |
| the signature value is checked (openssl `-nosigs`) | 41 | 1 | **0** | 0 |
| the certificate window is checked at the claimed time | 40 | 1 | **0** | 0 |
| `--require-timestamp` is read | 38 | 1 | **3** | 0 |
| the `mimetype` is compared | 39 | 1 | **0** | 0 |
| a chain failure is reported as undecided, not as a refusal | 36 | 3 | **1** | 0 |
| the operator exclusion is made over EVERY signer, not the first | 42 | 1 | **0** | 0 |
| a signer certificate that is a CA is refused | 43 | 1 | **0** | 0 |
| every certificate in the chain is date-checked at the claimed time | 44 | 1 | **0** | 0 |
| the TSA's own chain is date-checked at the claimed time | 45 | 1 | **0** | 0 |
| a duplicate ZIP entry name is refused | 46 | 1 | **0** | 0 |
| a covered path that leaves the package is refused | 47 | 1 | **0** | 0 |
| the signature's CONSTRUCTION is read (shape check removed) | 48 | 1 | **0** | 0 |
| a CRL entry is compared to the certificates in the chain | 49 | 1 | **0** | 0 |
| the coverage test — a CRL only speaks for the CA that issued it | 51 | 3 | **0** | 0 |
| a CRL's window is checked (`nextUpdate`, `thisUpdate`) | 52 | 3 | **0** | 0 |
| the unarmed revocation state is printed as unarmed | 50 (unarmed) | names the unarmed state | **prints "checked CLEAN" with nothing checked (still exit 0)** | 0 |

The last row is the shape the previous review found broken for the signer set, and it is here on
purpose: an **unarmed** check must never read as a pass, and the exit code cannot carry that — the
mutant still exits 0 on vector 50's unarmed arm while printing "checked CLEAN" over material it never
read. The two arms' `must print` lists are the instrument: on the armed arm "checked CLEAN …" is
present and the unarmed sentence is absent, and on the unarmed arm exactly the reverse.

The `-nosigs` row is the one that matters most: it is a copy in which `openssl cms -verify` parses the
SignedData, finds the signer, builds the chain and does not check the signature — and vector 41 then
passes. The signature check is load-bearing, and `--debug` prints the exact command that performs it.

## The validator runs on a second shell and a second awk

The whole vector suite above was re-run under `busybox sh` with `busybox awk`, `sed`, `grep`, `cmp`
and `sha256sum` — a different shell and a different awk implementation from the ones used for the
table. All 44 invocations of `martelage-verify` (33 vector runs plus the 11 documented second arms) return
the same exit code, and 43 of 44 produce byte-identical stdout and stderr. The exception is measured and named:
vector 16, a NUL byte inside a record body, is refused by both awks (exit 1) with different refusal
text, because `busybox awk` and `gawk` split a NUL-bearing line differently. That is a difference
between two awks' handling of a byte no conformant package may carry, not a difference in the
verdict. That is what "POSIX shell and coreutils" is supposed to mean, so it was measured rather than
asserted.

One discrepancy, disclosed rather than reconciled: the figure above is 44, and a mechanical
enumeration of the `martelage-verify` invocations documented in today's `expected.txt` files finds
**46** across vectors 01–33 (33 primary runs and 13 second arms — vector 30 documents four arms, not
two — plus 2 base-validator arms inside the P3 vectors, for 48 in the whole tree). The busybox
comparison was not re-run to settle which figure the old count was enumerating, so the 44 above is
left as it was measured and the enumeration here is stated separately, with both numbers in view.

That claim is about `martelage-verify` and stops there: `p3-verify` is 41 further invocations under
`python3` and the `openssl` binary, which is a different dependency class and is not offered as a
POSIX-shell result. (The count is every invocation the vectors' `expected.txt` files document,
enumerated mechanically: 2 arms per vector for 34–47 except 39 with 3, plus 12 for 48–52.)

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

## Licence

This repository carries **two** licences, split by what a file is, and the split is stated in
[`LICENSE`](LICENSE): the specification text ([`spec/MARTELAGE-0.1.md`](spec/MARTELAGE-0.1.md)),
the test vectors under [`vectors/`](vectors/) and this README are **CC BY 4.0**
([`LICENSE-CC-BY-4.0`](LICENSE-CC-BY-4.0)); the reference validator
([`validator/martelage-verify`](validator/martelage-verify)) and all other code are **Apache-2.0**
([`LICENSE-APACHE`](LICENSE-APACHE)). The split is deliberate: a standard's text should be
quotable and its code should be reusable, and the two licences are chosen for those two jobs
separately.

**GitHub's licence badge reads `NOASSERTION` on this repository.** That is what a per-file split
looks like to a detector that expects one SPDX identifier for the whole repository — it is not a
statement that the work is unlicensed. If you see `NOASSERTION`, read [`LICENSE`](LICENSE): it is
the authoritative statement of which paths carry which licence.

## Raising a defect

Open an issue against the sentence, not the code: quote the `MA-` identifier and the text, and say
what it lets a producer or a verifier claim that the format cannot deliver. A defect report that
shows a mechanism implying more than it buys is the most valuable kind, because that is the failure
mode this standard exists to prevent.
