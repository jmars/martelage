# MARTELAGE-0.1 — The Evidence Package Standard

**Status:** draft 0.1 — published for adoption and criticism. Not yet a stable standard.
**Identifier of this document:** `martelage 0.1`. The wire identifier of the package format it defines is
`"standard":"martelage","v":1`.
**Licence:** this specification text is licensed CC BY 4.0; the reference validator and all code in
this repository are licensed Apache-2.0. See `LICENSE`.
**Editors:** the Martelage authors. See `README.md` for how to raise a defect against this text.

---

## 0. How to read this document

**0.1 Requirement keywords.** The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD,
SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted
as described in RFC 2119 and RFC 8174, and only when they appear in capitals. — **MA-1**

**0.2 A SHOULD with a stated reason is conformant.** Where this document says a producer SHOULD do
something, and the producer instead states in the package why it did not, the package is
conformant. A SHOULD is a request with an argument attached; an argument answered is not a defect.
Where the reason is not stated, a validator MAY report the omission as a finding. — **MA-2**

**0.3 Every normative requirement has an identifier.** Requirements are marked `MA-<n>`. A
conformance report MUST cite the identifier of every requirement it reports as met or unmet; a
clause that cannot be cited cannot be tested. Identifiers are permanent: a withdrawn requirement
keeps its number and is marked withdrawn; numbers are never reused. — **MA-3**

**0.4 Three claim classes.** Text in this document and in a conformance report is one of:
**MEASURED** (observed on an artifact, with the artifact named), **INTERPRETATION** (a reading of a
document or a law), **PROJECTION** (a prediction). The informative annexes mark their claims; the
normative body states limits rather than achievements, and therefore carries no measurements at
all. — **MA-4**

**0.5 What this document is not.** This standard does not define a record format. It does not say
what an auditable system should record, in what schema, or with what semantics. It defines a
*package*: the outer layer that carries someone else's records, states its own scope, chains itself
to the packages before it, and records whether anyone outside the producer holds its digest. The
record grammar is the payload's own business and is named, not specified, here. — **MA-5**

---

## 1. Terms

**Package.** A directory (see §3) holding one manifest and at least one payload file.

**Manifest.** The single file `package.json` that lists every other file in the package with its
digest, states the package's scope and anchor, and names its place in a package chain.

**Payload file.** Any file listed in the manifest. A payload file whose `role` is `records` is a
*record stream file* and MUST conform to §6; every other role is carried and hashed but not parsed.

**Record.** One JSON object on one line of a record stream file, carrying an envelope (§6.2) around
a body chosen by the payload's own record contract.

**Stream.** A named, independently hash-chained sequence of records inside one record stream file.
Streams are per writer and per subject-matter; two writers' records are never merged into one
stream (§6.6).

**Sequence.** The 1-based position of a record within its stream, with no gaps.

**Predecessor digest.** The digest of the previous record in the same stream, carried by each
record, which is what makes an interior removal visible.

**Package digest.** `sha256` over the exact bytes of the manifest. It transitively pins every file
in the package, because the manifest lists every file's digest.

**Package chain.** The ordered relation between packages, each recording the package digest of its
predecessor.

**Scope statement.** The manifest section that says what the package contains and — separately —
what it does not, each absence carrying a meaning from a fixed vocabulary (§8.3).

**Anchor statement.** The manifest section that says whether a party other than the producer holds
this package's digest, and under which named profile (§9.3).

**Producer.** The program and the party that assembled the package. **Operator.** The party with
administrative control of the machine the producer ran on. They are usually the same party and this
standard assumes they are (§2).

**Verifier.** Whoever runs a validator against a package. A verifier is not the producer and is not
trusted by the producer to be anything in particular.

---

## 2. Conformance

**2.1 What conformance is.** A package is conformant with MARTELAGE-0.1 when all of the following hold.
There is no other definition, no level above it and no level below it. — **MA-6**

1. It is a directory containing `package.json` and at least one record stream file (§3).
2. The manifest is canonical JSON (§5.1) with the required fields of §5.2, and its scope (§8) and
   anchor (§9) sections use the vocabularies defined here.
3. Every file listed in the manifest is present with the listed byte length and `sha256` (§4.4).
4. Every record stream file is a well-formed envelope stream (§6): line 1 is a stream manifest, and
   the records form per-stream sequences 1..n with no gaps and a correct predecessor chain (§6).
5. A validator implementing §10 reports it conformant (exit code 0) when run with no verifier inputs
   beyond the package directory.

**2.2 Conformance is not a claim about the records.** A conformant package MAY contain records that
are false, and MAY omit records that existed. Conformance says the package is *well-formed and
self-consistent*; it says nothing about truth or completeness (§7.2.3, §10.7). — **MA-7**

**2.3 There is one level, deliberately.** This standard has no maturity ladder. A ladder reads as
"the lower tier is deficient", which is backwards: the unanchored tier is the adoption surface, and
the anchor is an optional slot inside it (§9.1). — **MA-8**

**2.4 How a third party claims conformance.** By publishing a statement, in its own name, that its
producer emits packages conformant with `martelage 0.1`, and naming the requirements it relies on and any
it does not satisfy with the reason. No registration, no permission and no fee is required. A
conformance statement is a claim under the claimant's own name; this standard does not certify
anyone. Annex C is the template. — **MA-9**

---

## 3. The threat model

The threat model comes first because every mechanism below is derived from it, and because a format
that names its adversary can be argued with while a format that does not cannot.

**3.1 The adversary is the operator.** Assume the party that produced the package also has
administrative control of the machine it was produced on. That party can rewrite the system's
records, its auxiliary state, the exported files, the manifest, and the producing binaries. They can
therefore recompute every digest inside a package, correctly and consistently. — **MA-10**

**3.2 Nothing inside a package proves anything against that party acting coherently.** A digest
recomputed by the adversary matches. An internal consistency check that the adversary satisfies
passes. This is not a defect to be designed away; it is the residual every mechanism below is
measured against, and no clause in this document may imply otherwise. — **MA-11**

**3.3 The residual sentence.** Every validator conforming to this standard MUST print the following
two sentences, verbatim, on every run **that names a package**, including a run that reports the
package conformant, and including a run that ends at exit code 2 because the package could not be
read: the residual is not a claim about the package, so it is not dropped when the report is. A run
that names no package at all — a usage error before a target is known — has nothing to report on.
— **MA-12**

> A package proves that what it contains was not altered after it left; it cannot prove that what it
> contains is all there was, and against an operator who rewrote everything before the first anchor
> it proves nothing.
>
> A coherent tamper performed before the first observation is invisible to every mechanism in this
> standard.

**3.4 The five mechanisms, each with its exact power.** Each mechanism below MUST be specified and
reported separately, because their powers differ by orders of magnitude and a reader will otherwise
credit the weakest with the strength of the strongest.

| # | Mechanism | What it buys | What it does not |
|---|---|---|---|
| i | Internal consistency (§5.1–5.2, §6.2, §7.1–7.2) | A partial or sloppy rewrite shows as a break: a moved body digest at a fixed position, a gap, a count that disagrees with the payload. | A wholesale, internally consistent rewrite passes. |
| ii | Staleness against the previous package (§7.4) | Converts an invisible omission into a break visible one package later — if someone kept the earlier package. | An operator who starts a fresh chain and was watched by nobody. |
| iii | Witnesses outside the audited subject (§3.6) | Forces the operator to rewrite *more* places consistently. | Stops the operator. Each extra rewrite is another place to contradict a copy someone else holds — it multiplies cost, never prevention. |
| iv | The enrollment gap (§3.5) | Nothing. It is named so it is not hoped away. | — |
| v | The external anchor (§9) | Proves a digest existed at a time, held by someone other than the operator. | Truth, completeness, or that the operator told the witness everything. |

**3.5 The enrollment gap, named not hoped away.** A coherent tamper performed before the first
observation of the subject, and before the first anchor exists, is undetectable by any local
mechanism in this standard. This is stated in the normative body, printed by every validator
(§3.3), and MUST NOT be described anywhere in a conformance report as covered. — **MA-13**

**3.6 Witnesses outside the audited subject.** A mechanism of class (iii) is any token, counter or
ledger that a party the audited subject cannot write supplies, and that the record must be
consistent with. Its power is exactly cost multiplication: an invented record must wear a token the
witness never issued, or agree with a counter the witness never moved. Where the witness runs on the
same host as the subject, it is inside the operator's reach and its power is bounded accordingly; the
package MUST say where a witness runs, **in band**: in a `bound[]` entry or in the scope statement,
naming the witness and the host it runs on. This standard defines no field for it, and no validator can
check it — whether a token was issued, and from which host, is not a property of the package's bytes,
so it is listed among what no validator can check (§10.7) and is the producer's claim under its own
name. Describing a same-host witness as an external anchor is forbidden. — **MA-14**

**3.7 What an anchor does and does not prove.** An anchor proves that a specific digest existed at a
specific time and was held by a party other than the operator. It never proves the record is true,
never proves the operator told the witness everything, and never proves completeness. A seal or a
timestamp produced by the operator's own key material is not an anchor against the operator: they
hold the key. — **MA-15**

---

## 4. The package

**4.1 The container is a directory.** A package is a directory, not an archive. A tar or zip of a
conformant directory is a conformant *transport*: unpack it and validate the directory. The reason
is stated so it is not relitigated: archives are not reproducible by construction (they carry member
mtimes and orderings), and a byte-identical re-production of an archive would be a claim the format
cannot keep, while the *file set* is reproducible and checkable with `sha256sum` alone. — **MA-16**

**4.2 Mandatory files.** — **MA-17**

* `package.json` — the manifest. Exactly one, at the package root.
* at least one record stream file — any path, listed with `"role":"records"`.

**4.3 Additive files.** A package MAY carry any number of further files, each listed in the manifest
with a role. A role this standard does not define is carried and hashed, and MUST NOT be parsed by a
validator that does not know it. — **MA-18**

**4.4 The manifest lists every file.** Every file in the package except `package.json` itself MUST
appear exactly once in `files[]` with its `path` (relative, `/`-separated, no `.` or `..` segment,
not absolute), its `sha256` (64 lowercase hex characters), its `bytes` (decimal) and its `role`. A
validator MUST refuse a package with a listed file absent, a listed digest that does not match, a
listed length that does not match, or an unlisted file. — **MA-19**

Every entry in a package MUST be a regular file or a directory: a symbolic link MUST be refused
whether `files[]` lists it or not, because a link's bytes are its target's bytes, and a target can be
replaced or re-pointed without changing any byte the manifest lists — and may lie outside the package
altogether. — **MA-82**

**4.5 No validator inside the package.** A package MUST NOT be required to carry a validator, and a
validator found inside a package proves nothing about that package: it is inside the directory the
operator can rewrite. Checkability comes from the published reference validator or from the
verifier's own implementation of this document, obtained through a channel the operator does not
control. — **MA-20**

**4.6 The zero-tooling check.** Because the manifest is canonical and lists every file with its
digest, a verifier with nothing but a POSIX shell can check the file set without any validator:

```sh
grep -o '{"path":"[^"]*","sha256":"[0-9a-f]*"' package.json |
  sed 's/{"path":"\([^"]*\)","sha256":"\([0-9a-f]*\)"/\2  \1/' > SHA256SUMS
sha256sum -c SHA256SUMS
```

This is a normative property of the format, not an example: a manifest whose canonical form does not
admit that one-liner is non-conformant. — **MA-21**

---

## 5. The manifest

### 5.1 Canonical form

**5.1.1** `package.json` MUST be canonical JSON: UTF-8, no byte-order mark, no insignificant
whitespace anywhere outside string values (no spaces, tabs or newlines between tokens), no
duplicate keys, no trailing newline requirement either way (the digest is over the bytes as
written, and a producer MUST NOT change them after writing the manifest). — **MA-22**

**5.1.2** Keys MUST appear in the order given in §5.2, at the top level and inside every object the
schema names. Array order is meaningful where this document says so. The frozen order exists so that
a ~100-line reader can parse the manifest honestly and so that a manifest is byte-comparable across
implementations; a validator MUST refuse a manifest whose top-level or named-object key order
differs. — **MA-23**

**5.1.3** String escaping is frozen: `"` → `\"`, `\` → `\\`, byte `0x08` → `\b`, `0x09` → `\t`,
`0x0a` → `\n`, `0x0c` → `\f`, `0x0d` → `\r`, any other byte below `0x20` → `\u00xx` with lowercase
hex, every byte at or above `0x20` verbatim. A NUL byte anywhere in the manifest or a record stream
file is a refusal, not something to escape: it cannot be carried in a JSON string and silently
truncating it would edit the record. — **MA-24**

### 5.2 Fields

```
{"standard":"martelage","v":1,"kind":"package-manifest",
 "producer":{"id":…,"component":…,"version":…,"contract":…},
 "subject":{"id":…,"kind":…},
 "created_at":<epoch|null>,
 "prev":{"package_sha":<hex|null>,"how":"state"|"given"|"none"},
 "files":[{"path":…,"sha256":…,"bytes":…,"role":…},…],
 "scope":{"contains":[…],"not_contains":[{"thing":…,"meaning":…,"why":…},…]},
 "anchor":{"anchored":<bool>,"profile":<string|null>,"binds":<string|null>,"claim":<object|null>},
 "counts":{"files":<int>,"records":<int>,"streams":<int>},
 "bound":[…,…]}
```

**5.2.1 `standard`, `v`, `kind`.** `"standard"` MUST be `"martelage"`; `"v"` MUST be the integer format
version this manifest speaks; `"kind"` MUST be `"package-manifest"`. A validator that does not
support the stated `v` MUST refuse the package loudly, naming the version, and MUST NOT attempt a
best-effort parse. — **MA-25**

**5.2.2 `producer`.** Who assembled the package. `id` is the producing party or system's name,
`component` the program, `version` that program's version, `contract` the identifier and version of
the *payload's record contract* (for example `"<contract-id> <version>"`). The package standard and
the record contract are different layers, versioned independently (§11.1). — **MA-26**

**5.2.3 `subject`.** What the records are about. `id` MUST be a *content* identity of the subject —
a digest over the subject's own content identity, never a filesystem path, never a hostname, never
an account name. `kind` is the producer's classification of the subject. Publishing a path or a host
identity here is non-conformant, because a path is not part of a record and a subject identity that
names a machine invites reading the package as a record about a person. A validator MUST refuse an `id`
shaped like a path (a `/` segment, or a bare `.` or `..`), and MUST NOT report the rest as checked: it
cannot tell a digest from a hostname or an account name, so that half of this rule is the producer's
obligation and is listed among what no validator can check (§10.7). — **MA-27**

**5.2.4 `created_at`.** The producer's epoch at assembly, or `null` where it records none. A
timestamp MUST NOT be rendered as `0` to mean absent: a reader cannot tell "the epoch" from "the
producer records none", and the second is the honest answer. A validator MUST refuse a `created_at` of
`0`, and a record whose `ts` is `0` (§6.2 states the same rule for a record). — **MA-28**

**5.2.5 `prev`.** The predecessor package's digest and where that value came from: `"state"` (a
chain state file the producer keeps), `"given"` (a value supplied to the producer), `"none"` (no
predecessor). An unchained package MUST say so with `"package_sha":null,"how":"none"`; it MUST NOT
fabricate a chain, and a validator MUST refuse `package_sha` non-null with `how` equal to `"none"`
or `package_sha` null with `how` not equal to `"none"`. — **MA-29**

**5.2.6 `files`.** The file list of §4.4. `role` is a lowercase word; this standard defines
`records` (a record stream file) and reserves `document` (human-readable material carried with the
package) and `evidence` (verifier-side material the producer is passing along, never required for
conformance). — **MA-30**

**5.2.7 `scope`.** §8.

**5.2.8 `anchor`.** §9.

**5.2.9 `counts`.** `files` MUST equal the number of entries in `files[]`; `records` MUST equal the
number of record lines across all record stream files (line 1 of each such file is a stream
manifest, not a record, and is not counted); `streams` MUST equal the number of distinct stream
names across all record stream files — a stream that a stream manifest declares is one of them, empty
or not. A disagreement is a refusal. — **MA-31**

**5.2.10 `bound`.** An array of short strings: the producer's own stated limits, in band, so a
consumer cannot miss them. It MUST be present and MUST NOT be empty; a producer with nothing to
state writes the residual of §3.3 into it. — **MA-32**

**5.2.11 Unknown fields.** A reader MUST ignore any key it does not know, anywhere, count what it
ignored per `(object, field)`, and be able to report the counts. An ignored field is never guessed
at and never causes a record or a file to be dropped. A validator that knows only this version
refuses a manifest whose `v` it does not support (§5.2.1) and otherwise ignores and counts. —
**MA-33**

---

## 6. The envelope and the payload

**6.1 The payload is the producer's own record stream, carried verbatim.** This standard does not
re-render, normalise or merge a record. A package carries the bytes a producing system emitted. The
consequence is deliberate: a package can never be a second author of the record, and a consumer
never has to ask which of two renderings of the same fact is authoritative. — **MA-34**

**6.2 The envelope.** Every record is one JSON object on one line, with exactly these keys in this
order: — **MA-35**

```
{"v":1,"kind":K,"stream":S,"seq":N,"id":"S:N","writer":W,"mark":M,"ts":T,
 "body":{…},"body_sha":"<64 hex>","prev":"<64 hex>"|null}
```

| key | meaning |
|---|---|
| `v` | the *payload contract's* version, not this standard's. |
| `kind` | the record kind. At payload contract v1, `kind` and `stream` are equal; they are separate keys so a later version can carry several kinds on one chain without renaming anything. |
| `stream` | the chain the record belongs to: `^[A-Za-z][A-Za-z0-9_.-]*$`. |
| `seq` | position within the stream, starting at 1, no gaps. |
| `id` | `"<stream>:<seq>"` — the record's stable name. |
| `writer` | who produced the underlying fact. Non-empty; `^[A-Za-z][A-Za-z0-9_.|/-]*$`. |
| `mark` | the record's provenance class: `MEASURED` (read from something a writer wrote), `DERIVED` (computed from records, the computation named in the body), `ABSENT` (a stream that is not there — only on a stream manifest entry), `UNKNOWN` (a kind this contract version does not know, carried verbatim). |
| `ts` | the writer's own epoch, or `null` where the writer records none. Never `0`-rendered: an absent timestamp is not the epoch. |
| `body` | the record's own content, a JSON object, in the payload contract's schema. |
| `body_sha` | `sha256` over the canonical body bytes exactly as they appear in the line. |
| `prev` | the `body_sha` of the previous record in the same stream; `null` at `seq` 1. |

**6.3 A record is only ever written complete.** A producer MUST assemble a record stream before its
first byte leaves the producer, so that a cut can never be presented as a short-but-complete stream,
and a verifier may treat any line that does not parse as a transport fault rather than as a record.
A truncated final line, a line that does not match §6.2's shape, or a record whose keys are not in
the frozen order is a refusal. — **MA-36**

**6.4 The stream manifest.** Line 1 of each record stream file is a JSON object that declares the
payload's own contract. It MUST carry `contract` (the record contract's identifier) and `v` (its
version) as its first two keys, and it MUST carry `streams`: an object mapping each stream name in
this file to `{"n":<count>,"head":"<64 hex>"|null}`, where `head` is the `body_sha` of the stream's
last record and `null` for an empty stream. It MAY carry anything else, which this standard does not
constrain and a validator MUST NOT interpret beyond ignoring and counting it. — **MA-37**

**6.5 Line 1 is not a record.** A stream manifest MUST NOT be counted as a record, MUST NOT be
assigned a sequence number, and MUST NOT be chained. — **MA-38**

**6.6 One stream per writer per subject-matter; never a merged stream.** Records produced by
different writers MUST NOT be merged into one stream, and a producer MUST NOT renumber, re-chain or
interleave two writers' records into a single chain. If two writers' records must travel together,
the package carries two record stream files, and a validator checks each independently and reports
any disagreement between them as a finding (§10.5). A merge would manufacture an agreement between
writers that neither wrote. — **MA-39**

**6.7 The seam rule.** A package MAY carry more than one record stream file. Each is validated on
its own; two files MUST NOT be read as a continuation of one another even when they declare the
same stream name. Two files declaring the same stream name with different records at the same `seq`
is a *finding*, reported with both file names and the sequence number, never resolved by choosing
one. — **MA-40**

---

## 7. Hash continuity: the layers, and exactly what each proves

The layers are numbered because their powers differ and a reader will otherwise credit the weakest
with the strength of the strongest. Every validator report MUST show which layers were armed
(§10.4 item 6), and MUST NOT let an unarmed layer read as a pass.

### 7.1 Layer 0 — the record body

**7.1.1** `body_sha` is `sha256` over the canonical body bytes exactly as they appear in the line.
A verifier re-hashes the body it received and MUST get the same value. — **MA-41**

**7.1.2 What it stops:** alteration of any carried record's content, and any rewriting that leaves
the body digest where it was. **What it does not stop:** removal, insertion or re-ordering of whole
records — nothing about a body digest says another body was not beside it. — **MA-42**

### 7.2 Layer 1 — the stream

**7.2.1** Within a stream, `seq` runs 1..n with no gaps; `prev` is `null` at `seq` 1 and otherwise
the previous record's `body_sha`; and the stream manifest's `n` and `head` MUST agree with the
records actually present. — **MA-43**

**7.2.2 What it stops:** removal, insertion or re-ordering of records *within a stream as
presented*. A removed interior record breaks `prev`; a re-ordered one breaks `seq`; a truncated tail
breaks `n` and `head`. **What it does not stop:** a wholesale stream rewrite with every digest
recomputed. — **MA-44**

**7.2.3 The headline limitation, stated as a requirement.** A chain proves order and integrity over
what is present. It does not prove completeness: a consistently-chained prefix, and a consistently
chained subset, pass every check in layers 0 and 1. This is not a defect to be designed away; it is
the residual that layers 3 and 4 bound, and no text in a package, a report or a conformance
statement may claim otherwise. — **MA-45**

**7.2.4 Timestamps are finding-level, not refusal-level.** Within a stream, a writer's `ts` values
SHOULD be non-decreasing. A violation MUST be reported as a finding with the writer, stream and
sequence numbers, and MUST NOT by itself make a package non-conformant: legitimately late-written
records with older epochs exist, which is the same reason chains are per stream rather than global.
— **MA-46**

### 7.3 Layer 2 — the package

**7.3.1** The package digest is `sha256` over the exact bytes of `package.json`. There is no
circularity: the manifest carries no self-digest, and because it lists every other file's digest,
the package digest transitively pins every file, including the scope statement and the anchor
claim. — **MA-47**

**7.3.2 What it stops:** any alteration of the package as a whole — a swapped record file, an edited
scope statement, a dropped payload file — because `files[]` no longer matches. **What it does not
stop:** production of a different, internally perfect package from scratch. A digest over the
payload alone was considered and rejected: it would leave the scope and anchor statements editable
without any visible effect. — **MA-48**

### 7.4 Layer 3 — the package chain

**7.4.1** Each package records its predecessor's package digest in `prev.package_sha`, and states in
`prev.how` where that value came from. — **MA-49**

**7.4.2** When a verifier holds the predecessor package, the validator MUST check that the current
package's `prev.package_sha` equals the predecessor's package digest, and that every stream present
in the predecessor is present in the current package as a *prefix*: the first `n` records of the
current stream MUST have the same `body_sha` sequence as the predecessor's stream, and the
predecessor's head MUST still be present at the same position. A failure of either is
non-conformance. — **MA-50**

**7.4.3 What it stops:** silent omission and back-dated rewriting *across* packages, visible one
package later — if someone kept the earlier package. **What it does not stop:** a fresh chain by an
operator nobody was watching, which is exactly what `prev.how` discloses. — **MA-51**

### 7.5 Layer 4 — the external anchor

Defined in §9. It is the only layer whose witness the operator cannot recompute, and it still never
says the record is true or complete: it says a digest existed, at a time, by someone else. —
**MA-52**

### 7.6 The one-line reading of the table

Layers 0–2 stop tampering *with a package you hold*; layer 3 bounds tampering *across packages a
verifier held*; only layer 4 binds the package to a party outside the operator's reach. — **MA-53**

---

## 8. The scope and absence statement

**8.1 Why it is mandatory.** A package that omits this section reads as complete, and completeness
is the one thing no hash chain can ever say. An absence a consumer mistakes for "there is nothing"
is worse than a gap that is named. — **MA-54**

**8.2 Schema.** — **MA-55**

```
"scope":{"contains":["<one line per record family carried, naming the streams>",…],
         "not_contains":[{"thing":…,"meaning":<word>,"why":…},…]}
```

`contains` MUST be a non-empty array of non-empty strings. `not_contains` MUST be present, as an
array; it MAY be empty only where the producer states in `bound` that it has nothing to exclude,
and a producer SHOULD name at least the absences it knows of.

**8.3 The vocabulary.** `meaning` MUST be one of the following words, whose meanings are fixed by
this standard and MUST NOT be redefined by a producer: — **MA-56**

| word | meaning |
|---|---|
| `not-recorded` | the producer holds no such record — a true none. |
| `none-this-scope` | such records exist but lie outside this package's declared scope. |
| `unreadable` | a read error, not an absence; never silently folded into an absence. |
| `ABSENT` | the input the caller did not name — therefore NOT-KNOWN, not none. |
| `UNKNOWN` | a thing the producer cannot see at all. |

A `meaning` outside this set is a refusal: a scope statement that cannot be parsed is worse than no
scope statement, because it reads as one. New words are additive (a validator that does not know a
word MUST refuse rather than guess, and this standard's own vocabulary is extended only by
publication, never by a producer's local choice). — **MA-57**

**8.4 An absence is never rendered as a zero and never as a claim that the thing does not
exist.** `not-recorded` and `ABSENT` are different facts and MUST be different words. — **MA-58**

**8.5 The validator checks membership and prints the section in full on every run.** — **MA-59**

**8.6 The scope is the producer's claim under its own name.** It cannot be verified mechanically: a
producer can lie about what it did not carry. The standard records this as a limit rather than
pretending otherwise, and a consumer MUST read the scope statement as an assertion by the producer,
not as a fact established by the package. — **MA-60**

---

## 9. The anchor slot

**9.1 The rules, stated as rules.** — **MA-61**

**(a) A package with no third party, no seal, no timestamp and no key material is fully
conformant.** The base tier is useful and checkable with nothing but a shell and a hash function.

**(b) No mandatory third party, no key custody, no network, no trust anchors in the base tier.**
Nothing in the conformance definition of §2.1 requires any of them.

**(c) The anchor is a slot with named profiles, not one vendor.** §9.3 names three profiles at this
version and leaves the slot open to others.

**(d) An unanchored package MUST say so**, and the validator MUST print it: an honest "alone" is a
conformant state and a misleading silence is not.

**(e) A claimed anchor the verifier cannot verify MUST NOT pass.** A package claiming an anchor whose
evidence is absent, whose profile is unknown, or whose verification fails, MUST NOT be reported
conformant (§10.3 exit codes 1 and 3).

**9.1a A claim MUST NOT carry a value derived from the package digest.** A manifest cannot contain
its own digest: any claim field holding the package digest, or an entry identifier assigned to that
digest, would change the digest that the field is supposed to bind, and the claim would be false the
moment it was written. Anchor evidence is therefore verifier-side by construction, and a claim
carries only what a verifier needs in order to go and obtain that evidence. A validator MUST refuse a
claim any of whose values is a bare 64-hex digest, whatever the field holding it is called: the name of
a field is not what makes a claim false, and a claim carries references and procedures, never a
digest. — **MA-62**

**9.2 Schema.** — **MA-63**

```
"anchor":{"anchored":<bool>,"profile":<string|null>,"binds":<string|null>,"claim":<object|null>}
```

When `anchored` is `false`: `profile`, `binds` and `claim` MUST all be `null`. When `anchored` is
`true`: `profile` MUST be the exact wire string of a profile of §9.3 — `p1-second-party-digest`,
`p2-append-only-log` or `p3-eidas-qualified-seal-asic-e` — or a profile published elsewhere and named
in `claim`; `binds` MUST be `"manifest-digest"` (the anchor binds `sha256` of the manifest bytes); and
`claim` MUST be an object in that profile's schema. The `P1`/`P2`/`P3` markings of §9.3 are labels for
those strings, never values: a manifest writing `P1`, `p1`, or a profile's name in any other spelling
is refused as an unknown profile (§9.4). Any other combination is a refusal.

**9.3 The profiles at this version.** Each profile has exactly one **wire string**: the value written
in `anchor.profile`, given below in code. That string is what a validator matches — no abbreviation, no
`P1` shorthand and no re-casing is accepted (§9.4). — **MA-64**

**P1, wire string `p1-second-party-digest`** — a digest of the package held by an identified party
other than the operator: a second host, a colleague's kept copy, a printed log line.
Claim: `{"holder":<id>,"held_at":<epoch|null>,"channel":<how the verifier can obtain the digest>}`.
Evidence: `--anchor-evidence` carrying the holder's digest (64 hex, or a file whose first 64-hex
token is that digest). The base validator verifies this profile fully: the holder's digest must equal
the package digest. This is the minimal adoptable anchor, and it costs one line kept by one other
machine.

**P2, wire string `p2-append-only-log`** — an entry in a ledger maintained by a party other than the
operator, of which a transparency log is one construction.
Claim: `{"log":<log id>,"inclusion":<how a verifier re-checks inclusion>,"held_at":<epoch|null>}`.
Evidence: the log's inclusion material, held by the verifier. The base validator can compare a digest
the log states to the package digest, and cannot re-check inclusion without the log: a digest that
contradicts the package is a refusal (exit code 1, §10.3), and a digest that matches still leaves
inclusion undecided, so it reports exit code 3 and names what it could and could not check (§10.3,
§10.4).

**P3, wire string `p3-eidas-qualified-seal-asic-e`** — an ETSI EN 319 162-1 ASiC-E container holding the package
files with a CAdES or XAdES signature over their digests, created by a legal person other than the
operator, with a qualified electronic time stamp and optional long-term validation.
Claim: `{"container":<reference>,"sealer":<legal person>,"seal":"qualified-electronic-seal",
"timestamp":"qualified"|"none","ltv":<bool>}`.
Evidence: the container plus the verifier's trust anchors. The base validator cannot verify a
signature — that needs a signature verifier and trust anchors — so it reports exit code 3 and names
the profile-specific verifier requirement. A profile-specific verifier MUST report under §10.

Three limits travel with P3 and MUST be stated wherever the profile is offered: **(i)** a seal made
with the operator's own key is worthless against the operator, because they hold the key; only a
seal by a different legal person, or a qualified time stamp, is out of their reach, and even then
the trust service attests only what it was handed; **(ii)** a single seal does not stop a re-forged
history — the operator can doctor a package and have *that* sealed; what defeats it is custody of
prior packages by the other party, so the seal multiplies the chain and does not replace it;
**(iii)** the legal presumption that attaches to a qualified seal is a presumption about integrity
and origin, not a technical guarantee of truth or completeness, and it MUST be kept distinct from
the residual of §3.3 in any document that cites both.

**9.4 An unknown profile name is an unverifiable claim.** A validator MUST refuse (exit code 1) a
package whose `profile` it does not know, rather than ignoring the claim. — **MA-65**

**9.5 An anchor is a relationship, not a package-intrinsic property.** "Anchored" is a property of
(package, verifier's evidence), not of the package alone: the same package is verified-anchored for a
verifier who brought the holder's digest and cannot be decided (exit code 3) for one who did not.
This consequence MUST be stated wherever the anchor is described, because it is the honest reading
of rule (e). — **MA-66**

**9.6 The anchor is never populated speculatively.** A producer with no witness MUST emit
`"anchored":false`. A placeholder, an empty claim or a claim over the producer's own key is worse
than an honest alone and is non-conformant. — **MA-67**

---

## 10. The validator contract

A package that cannot be checked is not one. The validator is part of this standard, not of any
producer.

**10.1 The reference validator.** `validator/martelage-verify` in this standard's repository, runnable
offline with a POSIX shell and the POSIX and coreutils utilities it uses — `awk`, `sed`, `grep`, `cmp`,
`sort`, `sha256sum`, `tr`, `cut`, `head`, `tail`, `wc`, `find`, `mktemp`, `rm`, `cat` — and nothing
else: no network, no interpreter beyond those, no key material, no service, no producer. This list is
normative in the same breath as the requirement: a validator that needs a tool outside it has left the
base tier, and the list MUST be corrected whenever the reference validator starts using one. It MUST
verify a base-tier package with no third party, no keys and no trust anchors present. — **MA-68**

**10.2 Inputs.** — **MA-69**

* the package directory (required, positional);
* `--prev-package DIR` — arms layer 3 (§7.4);
* `--anchor-evidence HEX|FILE` — arms the anchor profile's verification (§9.3);
* `--trust-anchors DIR` — arms P3's signature verification for a profile-specific verifier.

A verifier input strengthens one check and is never required for the base tier.

**10.3 Exit codes.** — **MA-70**

| code | meaning |
|---|---|
| `0` | **CONFORMANT** — every check the run could perform passed. An unanchored package exits 0; the NOT-ANCHORED line has been printed. |
| `1` | **NON-CONFORMANT** — a check failed: a digest, a length, a gap, a broken predecessor link, a torn line, a manifest count, an unknown scope word, an unsupported version, a chain break against `--prev-package`, a claimed anchor that is malformed or that the evidence contradicts. |
| `2` | **USAGE OR UNREADABLE** — the invocation is wrong, or an input could not be read (an unreadable file is not an absence). |
| `3` | **CANNOT DECIDE** — an input the validator needs to decide is absent: anchor evidence for a claimed anchor, trust anchors for P3, or a profile-specific verifier this validator is not. The validator MUST name the missing input. |

Exit code 3 exists because an instrument that cannot return "undecided" returns something else
instead. A claimed anchor that cannot be checked is neither conformant nor refuted, and reporting it
as either would be a false statement; it is not conformant enough to pass, so 3 is non-zero.

**10.4 The report.** On every run, in this order, a conforming validator MUST print: — **MA-71**

1. the package identity — package digest, standard and version, subject, producer, `created_at`,
   `prev` and `prev.how`;
2. the scope section in full, including every `not_contains` entry with its meaning word;
3. the per-file digest and length check result;
4. the per-stream continuity table — stream, record count, head, and the verdict for sequence,
   predecessor chain, identifier and stream-manifest agreement;
5. the anchor verdict — including the literal line
   `NOT ANCHORED — this package's digest is held by no one but its producer` for an unanchored
   package;
6. which layers were armed, and which were not, naming the layer and the missing input — for
   example `layer 3  package chain       not armed (no --prev-package given)`;
7. every refusal, each naming the check that failed and the file, stream and sequence that produced
   it;
8. any findings (§10.5), each naming the file, stream and sequence that produced it;
9. what the run **ignored**: every key it did not know, counted per `(object, field)` (§5.2.11,
   §11.5), as a section of its own — and reported as `none` where it ignored nothing;
10. what the run could **not decide**: every check it could not reach a verdict on, naming the missing
   input (§10.3). This section MUST be printed on **every** run that prints a report — in particular on
   a run that also reports refusals, where the undecided check is not what decides the exit code. A
   refusal must never make an undecided check invisible: exit code 1 and a missing input are two
   different statements about one package, and an honest report makes both;
11. the residual block of §3.3, verbatim;
12. the verdict.

**10.5 Findings are printed and are not non-conformance.** A *finding* is a fact the record shows
that is not a defect of the package: a non-monotone timestamp within a writer (§7.2.4), two record
stream files disagreeing about the same stream and sequence (§6.7), anchor evidence supplied for a
package that claims no anchor. A finding MUST be printed with the file, stream and sequence that
produced it, MUST NOT be silently passed, and MUST NOT change the exit code. — **MA-72**

**10.6 What the validator MUST be able to refuse.** Each of these is a gate arm of the reference
validator and a conformance requirement of any validator: a byte flipped in any payload file; a
dropped interior record; a re-ordered record; a truncated final line; a recomputed-but-short stream
(caught only by `--prev-package`, and the validator MUST say the layer was not armed when it was
not); an edited scope statement (the package digest moves); a forged anchor claim. — **MA-73**

**10.7 What every validator MUST admit it cannot check.** — **MA-74**

* whether the record is true;
* whether the package is complete — all that ever existed;
* anything that happened before the first observation or the first anchor (§3.5);
* the producer's binaries;
* the honesty of a witness, including a same-host witness (§3.6);
* where a witness runs, or whether it is outside the audited subject's reach (§3.6): the package can say
  so in `bound[]` or in its scope, and that statement is the producer's claim, not a checked fact;
* whether a `subject.id` is a digest rather than a hostname or an account name (§5.2.3): a validator
  refuses the path shapes it can see and cannot distinguish the rest;
* who may read the records: a payload's own readability classification is a classification by the
  publisher, and this standard enforces nothing about it. A validator only echoes it.

**10.8 A validator MUST NOT be required to know a producer.** Nothing in this contract depends on
identifying the program that wrote the package; `producer` is a claim under the producer's name.
— **MA-75**

---

## 11. Versioning and change policy

**11.1 Two layers, versioned separately.** The package standard (`"standard":"martelage"`, `"v":1`) and
the payload record contract (`producer.contract`) bump independently. A package may carry a new
record contract without a package version change, and a package version change does not touch the
record contract. — **MA-76**

**11.2 Additive only inside a version.** New optional manifest fields, new roles, new record kinds and
new streams are additions and do not change `v`: a reader that does not know one ignores it and counts
it (§5.2.11).

A **new value-level vocabulary word is additive to the document, not to an older validator.** A new
anchor profile name (§9.3) or a new `scope` `meaning` word (§8.3) is an addition to this standard, but it
is *not* ignorable by a validator that predates it: §9.4 (MA-65) and §8.3 (MA-57) require an unknown
profile or word to be refused, because guessing at a meaning is worse than refusing. The consequence MUST
be stated wherever such a word or profile is added — in this document and in a producer's own release
notes: **a package using one is refused by every conforming validator that does not yet know it**, loudly
and never as a silent misread (§11.4). Field-level and record-level additions are transparent to an older
reader; value-level additions are not, and a producer that needs an older validator to accept its
packages MUST NOT use one. — **MA-77**

**11.3 A version bump is for a change of meaning or a removal**, never for an addition. — **MA-78**

**11.4 An unsupported version is a loud refusal on both sides.** A producer refuses to emit a
version it does not speak; a validator refuses a package whose `v` it does not support, naming the
version, and never parses it best-effort. A silent misread of a changed meaning is worse than an
unavailable field. — **MA-79**

**11.5 The reader's rule.** A reader ignores unknown keys, counts what it ignored per `(object,
field)`, carries unknown record kinds verbatim with their bodies untouched, and refuses a version it
does not support. — **MA-80**

**11.6 What this document's own version means.** `martelage 0.1` is a *draft*: the normative requirements
are complete enough to implement against and to cite, and the change policy of §11.2–11.3 applies to
the wire format it defines from `v:1` onward. A change to a draft's requirement MAY be breaking; a
change to a published `v` MUST NOT be. A conformance statement MUST name both the document version
and the wire version it was made against. — **MA-81**

---

## Annex A (informative) — one implementation, measured

This annex names a specific system. It is informative: nothing here is required to conform, and
removing this annex would leave the standard whole.

**A.1 What it is.** `baliveau` is an append-only auditing system for a versioned deployment store. It
publishes its record through a read contract, `baliveau-cnc v1`, as JSON Lines on stdout from a tool
called `fx-export`. Baliveau is the first conformance case for MARTELAGE-0.1, not its definition.

**A.2 The payload is byte-compatible with §6 today — MEASURED against the emitter's source.**
`tools/fx-export.c` writes each record's envelope keys in exactly the order §6.2 requires, with
`body_sha` computed over the canonical body bytes as they are appended
(`emit_record`, `tools/fx-export.c:559–598`), and writes line 1 as
`{"contract":"baliveau-cnc","v":1,"kind":"manifest",…}` (`emit_manifest`,
`tools/fx-export.c:1666–1670`) — that is, `contract` and `v` first, as §6.4 requires, followed by a
`streams` object whose entries carry `n` and `head`. The canonical escaping rule and the NUL refusal
of §5.1.3 are the same rule the contract states for its own payload.

**A.3 What baliveau supplies to each layer.** MEASURED unless marked otherwise:

* Layer 0/1: `body_sha`, per-stream `seq`, `prev`, and stream `n`/`head` — as above. The system's own
  export gate re-derives a `body_sha` per stream with `sha256sum`, an implementation independent of
  the publisher's, so shell-checkability of the payload is proven in-tree rather than projected.
* Layer 2/3: a packager writes `package.json` and the payload, with `prev` taken from an out-of-store
  one-line chain state file or a supplied digest. INTERPRETATION: the chain state file is
  operator-writable like everything else on the host; it is a convenience for `prev`, not a control,
  which is why `prev.how` distinguishes `state` from `given`.
* Class (iii) witness: the system's host issues a per-boot nonce from a ledger the audited guest
  cannot write, and the audit accounting bounds appended records by the host's boot count. Per §3.6
  this is a same-host witness: it forces a coherent tamper to rewrite more places, and it is not
  claimed as an external anchor.
* The enrollment-gap sentence of §3.3 appears in the system's own audit output, in its own words,
  before this standard existed.
* Anchor: `anchored:false` at present. The system has no external witness in production, so per §9.6
  the slot stays empty. No eIDAS, no transparency log and no second-party holder is implemented;
  profiles P2 and P3 are specified, not built.

**A.4 What is not claimed.** No conformance report for baliveau is published in this repository yet;
the statement above is a description of an implementation, not a certification of one. A conformance
statement in the form of Annex C is the missing artifact.

---

## Annex B (informative) — prior art, surveyed from primary sources

Each quote below was read from the named primary source on 2026-10-30 during this standard's
research and is reproduced here as recorded then; it has not been re-read for draft 0.1, so treat the
wording as MEASURED-as-of-that-date and re-verify before quoting it in a normative argument. Each
entry states adopt / align / reject and the one decisive reason.

1. **in-toto / DSSE** — ALIGN in the anchor profiles, REJECT as the base. "Authenticates the message
   and the type to avoid confusion attacks. Avoids canonicalization to reduce attack surface."
   (DSSE README). Decisive for the reject: "Out of scope (for now at least): Key management / PKI" —
   DSSE presumes a signer holding key material, and the base tier has none. Adopted from it: sign
   the exact bytes (the anchor binds the package digest, never a re-canonicalised form), and its own
   verdict on JWS — "Too many insecure implementations and features" — which is why no profile here
   names JWS.
2. **SLSA provenance v1.0** — ALIGN the parsing rules, REJECT the ladder. "Consumers MUST ignore
   unrecognized fields unless otherwise noted." (§5.2.11 is the same rule.) Rejected because SLSA
   presumes a trusted builder — "The builder.id identifies this platform, representing the
   transitive closure of all entities that are trusted to faithfully run the build and record the
   provenance" — while this standard's adversary *is* the producer, so graded builder trust is the
   ladder §2.3 refuses.
3. **IETF SCITT (RFC 9943)** — ALIGN as the archetype of profile P2, REJECT as a dependency. "This
   document defines such an architecture for single-issuer signed statement transparency." A
   transparency service with signed statements and receipts is one legitimate instantiation of P2 and
   a service on the critical path for the base tier.
4. **W3C PROV-DM** — REJECT. "Provenance is information about entities, activities, and people
   involved in producing a piece of data or thing, which can be used to form assessments about its
   quality, reliability or trustworthiness." A graph interchange model: mapping onto it would
   re-render the record, which §6.1 forbids, and would drag a semantic-web toolchain into the check
   path. The envelope's `(writer, ts, body)` is entity-activity shaped, so a PROV rendering may
   later ride as an additive payload file with a role — out of scope at this version.
5. **CycloneDX** — ADOPT the completeness-vocabulary precedent, REJECT the format. "The aggregate of
   each composition can be described as complete, incomplete, incomplete first-party only,
   incomplete third-party only, or unknown." Evidence that a bill-of-materials standard needs a
   declared-completeness field at all; §8 is that field, with a finer vocabulary because "there were
   none" and "I cannot see" are different facts.
6. **SPDX 3.0.1** — REJECT. Its core model (Agent, Annotation, Artifact, Bom, Bundle, CreationInfo,
   Element, …) is an OWL/RDF model with a JSON-LD serialisation aimed at software-inventory
   interchange: wrong subject, and a toolchain an offline shell check cannot carry.
7. **OpenTelemetry logs** — REJECT the pipeline, ALIGN the philosophy. "OpenTelemetry defines a log
   data model. The purpose of the data model is to have a common understanding of what a LogRecord
   is…" and "we embrace existing logging solutions". OTel is a live collection pipeline; Martelage is a
   frozen offline export of a durable record. The affinity is real and worth naming: carry the
   writers' own shapes rather than inventing a new one.
8. **Trillian / Sigstore Rekor** — REJECT as a dependency, ADOPT as the archetype of P2. "Rekor's
   goals are to provide an immutable tamper resistant ledger of metadata generated within a software
   projects supply chain." An operated service — availability, network, an operator of the log — is
   the anti-adoption property for the base tier; the log's own maintenance-mode notice is survey
   evidence that operated logs are costly even for large ecosystems, which is why the log is one
   optional witness-side profile here.
9. **JWS (RFC 7515) / COSE (RFC 9052)** — REJECT from the base tier (both presume key material).
   COSE is the carrier SCITT already chose, so an adopter building P2 on SCITT gets COSE receipts
   without this standard profiling them. This standard names no signature envelope of its own beyond
   P3's ETSI CAdES/XAdES; adopting a second crypto envelope at this version would be vendor
   wrapping.
10. **eIDAS (Regulation (EU) No 910/2014) and ETSI EN 319 162-1** — ADOPT as profile P3 with the
    three limits of §9.3. The legal presumption attaches to integrity and origin of the sealed data,
    not to its truth or completeness, and the container standard defines both the simple and the
    extended associated-signature containers with a long-term-availability section.
11. **eIDAS 2.0 (Regulation (EU) 2024/1183)** — MEASURED to introduce the EU Digital Identity Wallet
    and qualified attestations of attributes about *persons*; PROJECTION: no change for a package at
    this version, because the seal, timestamp and preservation instruments P3 uses are the 910/2014
    ones and are untouched by it.

The design bias these eleven entries were tested against, and which they confirmed rather than
overturned: a format others will actually adopt is dependency-free, offline-checkable with a shell
and a hash function, and readable by a human without tooling. Anything requiring a service, a key
infrastructure or a specific runtime belongs in the optional slot, never in the conformance
definition.

---

## Annex C (informative) — conformance statement template

> `<Claimant>` states that packages produced by `<producer component, version>` conform to
> **MARTELAGE-0.1** (`martelage 0.1`, wire version `v:1`).
>
> Requirements satisfied: `<list of MA-n>`, or "all of §2.1".
> Requirements not satisfied, with reason: `<MA-n>: <reason>` or "none".
> Payload record contract: `<contract id> <version>`.
> Anchor profile in use: `<none | p1-second-party-digest | p2-append-only-log |
> p3-eidas-qualified-seal-asic-e>` — the exact wire string of §9.3, never the `P1`/`P2`/`P3` label; if
> none, "packages are emitted unanchored and say so".
> Validator used: `<reference validator, or the claimant's own implementation, naming it>`.
> Date: `<date>`. Contact: `<contact>`.
>
> This statement is a claim under the claimant's own name. It is not a certification by the Martelage
> authors, and it carries none of the residual limits of §3.3 away.

---

## Annex D (informative) — the test vectors shipped with this standard

`vectors/` holds packages constructed for this standard, not exported from any producer system. Each
directory carries an `expected.txt` naming the expected exit code and the requirement identifiers the
case exercises. `README.md` lists them with their expected and actual results, and records the
mutation of the reference validator that proves it can fail.

---

## Annex E (informative) — a worked minimal package, by hand

A conformant package with one record, written out with nothing but `printf` and `sha256sum`. This is
the whole of what a second project must produce to start.

```sh
mkdir -p pkg
# 1. the record's body, canonical (no whitespace, keys in the contract's order)
body='{"event":"started","detail":"hello"}'
# 2. its digest
bsha=$(printf '%s' "$body" | sha256sum | cut -c1-64)
# 3. the record line — envelope keys in the frozen order
printf '{"v":1,"kind":"note","stream":"note","seq":1,"id":"note:1","writer":"example","mark":"MEASURED","ts":1700000000,"body":%s,"body_sha":"%s","prev":null}\n' \
  "$body" "$bsha" > pkg/records.jsonl
# 4. line 1: the stream manifest (contract and v first, then streams)
printf '{"contract":"example-note","v":1,"kind":"manifest","streams":{"note":{"n":1,"head":"%s"}}}\n' \
  "$bsha" | cat - pkg/records.jsonl > pkg/r && mv pkg/r pkg/records.jsonl
# 5. the manifest — canonical, frozen order
recsha=$(sha256sum pkg/records.jsonl | cut -c1-64)
recbytes=$(wc -c < pkg/records.jsonl)
printf '{"standard":"martelage","v":1,"kind":"package-manifest","producer":{"id":"example","component":"by-hand","version":"0","contract":"example-note 1"},"subject":{"id":"%s","kind":"note-log"},"created_at":1700000001,"prev":{"package_sha":null,"how":"none"},"files":[{"path":"records.jsonl","sha256":"%s","bytes":%s,"role":"records"}],"scope":{"contains":["one note record on stream note"],"not_contains":[{"thing":"anything else","meaning":"not-recorded","why":"this package carries a single hand-written note"}]},"anchor":{"anchored":false,"profile":null,"binds":null,"claim":null},"counts":{"files":1,"records":1,"streams":1},"bound":["a package proves what it contains was not altered after it left; it cannot prove it is all there was"]}' \
  "$recsha" "$recsha" "$recbytes" > pkg/package.json
# 6. check it
sh validator/martelage-verify pkg
```

Two files, one shell, no network, no keys, no service. That is the adoption surface.

---

## Annex F (informative) — a second producer, priced in files

A project that already writes dated records to durable files needs exactly two things:

1. **An emitter** that puts its records into the envelope of §6.2: canonicalise each body, compute
   `body_sha`, assign `stream` and `seq`, wire `prev`, print the stream manifest first. For a project
   whose records are already one JSON object per line, this is roughly 80–120 lines in any language.
2. **A packager** that lists its files with digests, writes a canonical manifest with an honest
   scope, a `prev` from a one-line state file, and `anchored:false`: roughly 60–100 lines.

Production is decentralised and cheap; checking is centralised and shared. An adopter does not
reimplement the validator — it runs the published one, or reads it and writes its own against this
document. A sceptical adopter's own implementation is the standard working, not being replaced.
