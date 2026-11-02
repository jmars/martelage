#!/bin/sh
# mkp3.sh — rebuild the P3 vectors (vectors/34..41) from vectors/pki.
#
# Run after tools/mkpki.sh if you have regenerated the test PKI: the containers
# in those vector directories are sealed with keys that mkpki.sh replaces, so a
# fresh PKI means fresh containers.
#
#   sh tools/mkpki.sh && sh tools/mkp3.sh
#
# Offline. Needs `openssl`, `python3` and nothing else.

set -eu
LC_ALL=C
export LC_ALL

here=$(cd -- "$(dirname -- "$0")" && pwd)
repo=$(cd -- "$here/.." && pwd)
cd "$repo"

pki=vectors/pki
mk="python3 tools/mkasic.py"

# the one package every P3 vector seals. It is the base-tier example package
# from vector 01 with the anchor slot filled in as §9.2 requires, and nothing
# else touched.
mkpkg() { # $1: dir, $2: claim timestamp ("qualified"|"none"), $3: container reference, $4: ltv ("true"|"false")
	python3 - "$1" "$2" "$3" "${4:-false}" <<'PY'
import json, os, sys
out, ts, ref, ltv = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
src = json.load(open("vectors/01-minimal-conformant/pkg/package.json"))
src["anchor"] = {
    "anchored": True,
    "profile": "p3-eidas-qualified-seal-asic-e",
    "binds": "manifest-digest",
    "claim": {
        "container": ref,
        "sealer": "Witness AG",
        "seal": "qualified-electronic-seal",
        "timestamp": ts,
        "ltv": ltv == "true",
    },
}
os.makedirs(out, exist_ok=True)
for name in ("records.jsonl", "notes.md"):
    data = open(os.path.join("vectors/01-minimal-conformant/pkg", name), "rb").read()
    open(os.path.join(out, name), "wb").write(data)
open(os.path.join(out, "package.json"), "w").write(
    json.dumps(src, separators=(",", ":"), ensure_ascii=False) + "\n")
PY
}

# the vectors this script owns, in the order they are built. One list, because
# the removal pass, the guard below and any future pass must agree on it.
vectors="34-seal-verified 35-seal-digest-moved 36-anchor-untrusted 37-self-seal
         38-no-timestamp 39-container-malformed 40-signer-expired 41-signature-broken
         42-multisigner-operator 43-ca-signer 44-chain-expired 45-tsa-expired
         46-zip-duplicate 47-manifest-path-escape
         48-embedded-content 49-revocation-revoked 50-revocation-clean
         51-revocation-wrong-issuer 52-revocation-expired
         53-ocsp-revoked 54-ocsp-good 55-ocsp-expired 56-ocsp-unanchored-responder
         57-revocation-dir-partial 58-revocation-dir-garbage
         59-ltv-valid 60-ltv-absent 61-ltv-evidence-expired 62-ltv-missing-cert
         63-ltv-unclaimed-material 64-ltv-timestamp-unverified
         65-ltv-carried-revocation"

# expected.txt is HAND-WRITTEN: it is what the vector asserts, and a rebuild
# that lost one would leave a tree that still looks green while asserting
# nothing. That failure was once observed on a bad run of this script, so the
# state of every one is recorded before the first rm and compared after the last
# write; a rebuild that loses or alters an assertion aborts.
guard=$(mktemp "${TMPDIR:-/tmp}/mkp3.guard.XXXXXX")
trap 'rm -f "$guard"' EXIT HUP INT TERM
for v in $vectors; do
	[ -f "vectors/$v/expected.txt" ] || {
		printf 'mkp3.sh: vectors/%s/expected.txt is missing BEFORE the rebuild — refusing to run\n' "$v" >&2
		exit 1
	}
	sha256sum "vectors/$v/expected.txt" >>"$guard"
done

# remove the GENERATED parts only: the package directories and the containers.
for v in $vectors; do
	rm -rf "vectors/$v/pkg" "vectors/$v/pkg-moved"
	rm -f "vectors/$v"/*.asice
done
rm -rf vectors/57-revocation-dir-partial/material vectors/58-revocation-dir-garbage/material

# 34 — a container that verifies fully, with a checked timestamp
mkpkg vectors/34-seal-verified/pkg qualified seal.asice
$mk --package vectors/34-seal-verified/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --out vectors/34-seal-verified/seal.asice

# 35 — the seal is valid and the package has moved under it. pkg-moved is
# internally consistent (its own files[] digests are recomputed), so only the
# seal can see that it is not the package that was sealed.
mkpkg vectors/35-seal-digest-moved/pkg qualified seal.asice
$mk --package vectors/35-seal-digest-moved/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --out vectors/35-seal-digest-moved/seal.asice
rm -rf vectors/35-seal-digest-moved/pkg-moved
cp -a vectors/35-seal-digest-moved/pkg vectors/35-seal-digest-moved/pkg-moved
python3 - vectors/35-seal-digest-moved/pkg-moved <<'PY'
import hashlib, json, os, sys
d = sys.argv[1]
path = os.path.join(d, "notes.md")
data = open(path, "rb").read()
# one byte, in the middle of the document, and nothing else
data = data[:20] + bytes([data[20] ^ 0x01]) + data[21:]
open(path, "wb").write(data)
mf = json.load(open(os.path.join(d, "package.json")))
for entry in mf["files"]:
    blob = open(os.path.join(d, entry["path"]), "rb").read()
    entry["sha256"] = hashlib.sha256(blob).hexdigest()
    entry["bytes"] = len(blob)
open(os.path.join(d, "package.json"), "w").write(
    json.dumps(mf, separators=(",", ":"), ensure_ascii=False) + "\n")
PY

# 36 — a seal whose chain no supplied anchor reaches. Signed under root B;
# vectors/pki/anchors holds root A only.
mkpkg vectors/36-anchor-untrusted/pkg qualified seal.asice
$mk --package vectors/36-anchor-untrusted/pkg \
	--signer $pki/signerB.crt.pem --key $pki/signerB.key.pem \
	--timestamp --out vectors/36-anchor-untrusted/seal.asice

# 37 — a self-seal: the operator's own key made the seal
mkpkg vectors/37-self-seal/pkg qualified seal.asice
$mk --package vectors/37-self-seal/pkg \
	--signer $pki/operator.crt.pem --key $pki/operator.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --out vectors/37-self-seal/seal.asice

# 38 — a container with no timestamp, and a claim that says so
mkpkg vectors/38-no-timestamp/pkg none seal.asice
$mk --package vectors/38-no-timestamp/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--out vectors/38-no-timestamp/seal.asice

# 39 — three malformed containers over one package
mkpkg vectors/39-container-malformed/pkg qualified seal.asice
$mk --package vectors/39-container-malformed/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --break-mimetype application/zip --out vectors/39-container-malformed/seal-bad-mimetype.asice
$mk --package vectors/39-container-malformed/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --drop-entry records.jsonl --out vectors/39-container-malformed/seal-missing-entry.asice
# an entry the ZIP holds and the ASiC manifest does not cover: nothing binds its
# bytes, so it cannot be evidence of anything
$mk --package vectors/39-container-malformed/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --uncovered-entry notes.md --out vectors/39-container-malformed/seal-uncovered-entry.asice

# 40 — a signer whose certificate expired in 2021, sealed with a timestamp now
mkpkg vectors/40-signer-expired/pkg qualified seal.asice
$mk --package vectors/40-signer-expired/pkg \
	--signer $pki/expired.crt.pem --key $pki/expired.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --out vectors/40-signer-expired/seal.asice

# 41 — the manifest altered after it was signed, every stated digest intact
mkpkg vectors/41-signature-broken/pkg qualified seal.asice
$mk --package vectors/41-signature-broken/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --mutate-manifest --out vectors/41-signature-broken/seal.asice


# ── 42: TWO signers in one signature entry ──────────────────────────────
# The operator's own key as a CO-SIGNER behind a valid signer. A verifier that
# reads the first signer cert and calls that "the signer" reports the operator
# exclusion as checked while the operator co-signed. seal-two-signers.asice is
# the control: the same construction with a second sealer, no operator.
mkpkg vectors/42-multisigner-operator/pkg qualified seal.asice
$mk --package vectors/42-multisigner-operator/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--co-signer $pki/operator.crt.pem:$pki/operator.key.pem \
	--timestamp --out vectors/42-multisigner-operator/seal.asice
$mk --package vectors/42-multisigner-operator/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--co-signer $pki/signerC.crt.pem:$pki/signerC.key.pem \
	--timestamp --out vectors/42-multisigner-operator/seal-two-signers.asice

# ── 43: a CA certificate as the sealing party ───────────────────────────
# intermediateA is a CA (basicConstraints CA:TRUE, critical). It signs the
# manifest itself, so the chain reaches root A and only the CA flag is wrong.
mkpkg vectors/43-ca-signer/pkg qualified seal.asice
$mk --package vectors/43-ca-signer/pkg \
	--signer $pki/intermediateA.crt.pem --key $pki/intermediateA.key.pem \
	--chain $pki/rootA.crt.pem \
	--timestamp --out vectors/43-ca-signer/seal-ca-signer.asice

# ── 44: an intermediate that expired in 2021 ────────────────────────────
# The signer is valid; the certificate it chains through is not. The chain was
# verified with -no_check_time, so only a date check over the whole chain sees it.
mkpkg vectors/44-chain-expired/pkg qualified seal.asice
$mk --package vectors/44-chain-expired/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem \
	--chain $pki/intermediateA-expired.crt.pem \
	--timestamp --out vectors/44-chain-expired/seal-expired-intermediate.asice

# ── 45: a token from a TSA certificate that expired in 2021 ─────────────
# The seal and its chain are the ones vector 34 verifies; only the timestamping
# authority's certificate window differs.
mkpkg vectors/45-tsa-expired/pkg qualified seal.asice
$mk --package vectors/45-tsa-expired/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--tsa-config $pki/tsa-expired.cnf \
	--timestamp --out vectors/45-tsa-expired/seal-expired-tsa.asice

# ── 46: a duplicate ZIP entry name ──────────────────────────────────────
# notes.md appears twice: first with other bytes, then with the bytes the seal
# covers. zipfile.read() returns the last, a first-wins extractor writes the
# first, and the container says nothing about which copy is the evidence.
mkpkg vectors/46-zip-duplicate/pkg qualified seal.asice
python3 - vectors/46-zip-duplicate/pkg/notes.md vectors/46-zip-duplicate/shadowed-notes.md <<'PY'
import sys
data = open(sys.argv[1], "rb").read()
# one byte, in the middle of the document, and nothing else
open(sys.argv[2], "wb").write(data[:20] + bytes([data[20] ^ 0x01]) + data[21:])
PY
$mk --package vectors/46-zip-duplicate/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --shadow-entry notes.md=vectors/46-zip-duplicate/shadowed-notes.md \
	--out vectors/46-zip-duplicate/seal-duplicate-entry.asice

# ── 47: a manifest path that escapes the package root ───────────────────
# outside.txt sits BESIDE the package directory and the manifest covers
# '../outside.txt': the seal covers bytes the package does not contain, and the
# digest check follows the path out of the package and prints "match".
mkpkg vectors/47-manifest-path-escape/pkg qualified seal.asice
printf 'this file is not in the package. it sits beside it.\n' \
	>vectors/47-manifest-path-escape/outside.txt
$mk --package vectors/47-manifest-path-escape/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--manifest-entry ../outside.txt=vectors/47-manifest-path-escape/outside.txt \
	--timestamp --out vectors/47-manifest-path-escape/seal-path-escape.asice

# ── 48: a signature whose content is EMBEDDED, not detached ─────────────
# The same package, the same signer, the same timestamp as vector 34. One flag
# (`-nodetach`, via mkasic.py --embedded-content) puts the content INSIDE the
# CMS instead of leaving it detached over META-INF/manifest.xml — so the seal no
# longer presents the manifest as external content and the construction is not
# the one validator/p3-verify implements. seal-detached.asice is the control:
# the same build without that one flag.
mkpkg vectors/48-embedded-content/pkg qualified seal.asice
$mk --package vectors/48-embedded-content/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --embedded-content --out vectors/48-embedded-content/seal-embedded.asice
$mk --package vectors/48-embedded-content/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --out vectors/48-embedded-content/seal-detached.asice

# ── 49..52: revocation, from a CRL the verifier is HANDED ───────────────
# One construction, four arms, and the arms differ only in the revocation
# material: the signer is revoked, nothing is revoked, the CRL speaks for a
# different CA, the CRL has expired. The CRLs themselves are built by
# tools/mkcrl.sh (run by tools/mkpki.sh); nothing here is fetched.
for v in 49-revocation-revoked 50-revocation-clean 51-revocation-wrong-issuer \
         52-revocation-expired; do
	mkpkg "vectors/$v/pkg" qualified seal.asice
	$mk --package "vectors/$v/pkg" \
		--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
		--timestamp --out "vectors/$v/seal.asice"
done

# ── 53..58: revocation from an OCSP response, and from a directory ───────
# The same construction and the same package as 34 and 49..52. What differs is
# the revocation material: an OCSP response that reports the sealer revoked,
# one that reports it good, one whose window ended in 2021, one signed by a
# responder that chains to nothing, and two directories of mixed material. The
# responses are built by tools/mkocsp.sh (run by tools/mkpki.sh) with fixed
# dates; a directory holds COPIES of the files it is meant to hold, because the
# vector is a directory a verifier is handed, not a list of paths.
for v in 53-ocsp-revoked 54-ocsp-good 55-ocsp-expired 56-ocsp-unanchored-responder \
         57-revocation-dir-partial 58-revocation-dir-garbage; do
	mkpkg "vectors/$v/pkg" qualified seal.asice
	$mk --package "vectors/$v/pkg" \
		--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
		--timestamp --out "vectors/$v/seal.asice"
done

# 57: one CRL that speaks for the intermediate, one OCSP response that speaks for
# a certificate this chain does not contain. The sealer is left unspoken for.
mkdir -p vectors/57-revocation-dir-partial/material
cp $pki/crl-rootA-clean.pem vectors/57-revocation-dir-partial/material/
cp $pki/ocsp-signerC-good.der vectors/57-revocation-dir-partial/material/
chmod 644 vectors/57-revocation-dir-partial/material/*

# 58: the material a checking run needs, plus one file that is not revocation
# material at all — what a well-meaning operator leaves in a directory.
mkdir -p vectors/58-revocation-dir-garbage/material
cp $pki/crl-rootA-clean.pem vectors/58-revocation-dir-garbage/material/
cp $pki/crl-intermediateA-clean.pem vectors/58-revocation-dir-garbage/material/
chmod 644 vectors/58-revocation-dir-garbage/material/crl-*.pem
cat >vectors/58-revocation-dir-garbage/material/notes-from-the-operator.txt <<'EOF'
This file is not revocation material. It is a text file that a well-meaning
operator left in the directory beside the CRLs, and a verifier that reads every
file it was handed must say so rather than skip it.
EOF
chmod 644 vectors/58-revocation-dir-garbage/material/notes-from-the-operator.txt

# ── 59..64: LONG-TERM VALIDATION, from material the CONTAINER carries ────
# §9.3.1 (MA-84): when the claim states "ltv":true the container MUST carry, for
# every certificate of the established chain, revocation evidence (a CRL or an
# OCSP response) AND an RFC 3161 timestamp whose signature covers that evidence.
# --manifest-entry puts each file in the ZIP under META-INF/ltv/ AND lists it in
# the ASiC manifest, so the CAdES seal is what binds these bytes — that is why
# they are carried INSIDE the container instead of handed to the verifier on the
# command line. The material itself is built by tools/mklv.sh (called by
# tools/mkpki.sh); nothing here is fetched from anywhere.
ltv=vectors/pki/ltv
seal_ltv() { # $1: vector; the rest: "NAME=FILE" manifest entries carried by that arm
	v=$1
	shift
	mkpkg "vectors/$v/pkg" qualified seal.asice true
	args=
	for pair in "$@"; do
		args="$args --manifest-entry $pair"
	done
	# the pairs are complete arguments, never split: they hold no spaces
	# shellcheck disable=SC2086
	$mk --package "vectors/$v/pkg" \
		--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
		--timestamp $args --out "vectors/$v/seal.asice"
}

# 59 — COMPLETE, VALID and CORRECTLY TIMED material: one CRL for the sealer's
# issuer (intermediate A) and one for the intermediate's issuer (root A), each
# with an archival timestamp over its own bytes. Both CRLs are inside their
# windows at the time each timestamp establishes, so this is the arm that may
# pass, and its report names every value it validated
seal_ltv 59-ltv-valid \
	META-INF/ltv/crl-intermediateA-clean.pem=$ltv/crl-intermediateA-clean.pem \
	META-INF/ltv/crl-intermediateA-clean.pem.tst=$ltv/crl-intermediateA-clean.pem.tst \
	META-INF/ltv/crl-rootA-clean.pem=$ltv/crl-rootA-clean.pem \
	META-INF/ltv/crl-rootA-clean.pem.tst=$ltv/crl-rootA-clean.pem.tst

# 60 — the claim states ltv=true and the container carries NO validation material
# at all: the same construction as 34 with one claim field different. The claim is
# contradicted by the evidence it was supposed to carry
mkpkg vectors/60-ltv-absent/pkg qualified seal.asice true
$mk --package vectors/60-ltv-absent/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp --out vectors/60-ltv-absent/seal.asice

# 61 — material that is complete by count and OUT OF ITS WINDOW at the archival
# time: the sealer's CRL has nextUpdate 2021-01-01 and the timestamp over it is
# stamped later, so at the moment that timestamp establishes the CRL had already
# expired. One file differs from 59 and nothing else
seal_ltv 61-ltv-evidence-expired \
	META-INF/ltv/crl-intermediateA-expired.pem=$ltv/crl-intermediateA-expired.pem \
	META-INF/ltv/crl-intermediateA-expired.pem.tst=$ltv/crl-intermediateA-expired.pem.tst \
	META-INF/ltv/crl-rootA-clean.pem=$ltv/crl-rootA-clean.pem \
	META-INF/ltv/crl-rootA-clean.pem.tst=$ltv/crl-rootA-clean.pem.tst

# 62 — an OCSP response for the SEALER and its archival timestamp, and nothing at
# all for the intermediate: the material covers part of the chain and the arm
# names the certificate it does not cover. It is also the arm that exercises the
# carried OCSP path rather than the carried CRL path
seal_ltv 62-ltv-missing-cert \
	META-INF/ltv/ocsp-signerA-good.der=$ltv/ocsp-signerA-good.der \
	META-INF/ltv/ocsp-signerA-good.der.tst=$ltv/ocsp-signerA-good.der.tst

# 63 — the SAME complete material as 59 under a claim that states ltv=false: a
# finding, never a refusal, because the package makes no LTV claim for the
# material to support. The control for "carried material alone never refuses".
# The claim is filled in as true first and then set to false, so the package is
# byte-identical to 59's except in that one field
mkpkg vectors/63-ltv-unclaimed-material/pkg qualified seal.asice true
python3 - vectors/63-ltv-unclaimed-material/pkg/package.json <<'PY'
import json, sys
path = sys.argv[1]
mf = json.load(open(path))
mf["anchor"]["claim"]["ltv"] = False
open(path, "w").write(json.dumps(mf, separators=(",", ":"), ensure_ascii=False) + "\n")
PY
# the container above was sealed over the ltv=true package, so it is rebuilt over
# the claim that says false: one claim field differs from 59, and nothing else
$mk --package vectors/63-ltv-unclaimed-material/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp \
	--manifest-entry META-INF/ltv/crl-intermediateA-clean.pem=$ltv/crl-intermediateA-clean.pem \
	--manifest-entry META-INF/ltv/crl-intermediateA-clean.pem.tst=$ltv/crl-intermediateA-clean.pem.tst \
	--manifest-entry META-INF/ltv/crl-rootA-clean.pem=$ltv/crl-rootA-clean.pem \
	--manifest-entry META-INF/ltv/crl-rootA-clean.pem.tst=$ltv/crl-rootA-clean.pem.tst \
	--out vectors/63-ltv-unclaimed-material/seal.asice

# 64 — complete material in which the ARCHIVAL TIMESTAMP over the intermediate's
# CRL does not verify: one byte of its signature is flipped as the entry is
# written, so the token still parses and still states which bytes it is about, and
# only its own signature is broken
mkpkg vectors/64-ltv-timestamp-unverified/pkg qualified seal.asice true
$mk --package vectors/64-ltv-timestamp-unverified/pkg \
	--signer $pki/signerA.crt.pem --key $pki/signerA.key.pem --chain $pki/intermediateA.crt.pem \
	--timestamp \
	--manifest-entry META-INF/ltv/crl-intermediateA-clean.pem=$ltv/crl-intermediateA-clean.pem \
	--manifest-entry META-INF/ltv/crl-intermediateA-clean.pem.tst=$ltv/crl-intermediateA-clean.pem.tst \
	--manifest-entry META-INF/ltv/crl-rootA-clean.pem=$ltv/crl-rootA-clean.pem \
	--manifest-entry META-INF/ltv/crl-rootA-clean.pem.tst=$ltv/crl-rootA-clean.pem.tst \
	--corrupt-entry META-INF/ltv/crl-rootA-clean.pem.tst \
	--out vectors/64-ltv-timestamp-unverified/seal.asice

# 65 — the material the container carries says the SEALER WAS REVOKED: the CRL for
# intermediate A carries the one entry 49's arm carries, with an archival timestamp
# over it, and the rest of the material is 59's. A positive statement of revocation
# from the package's own evidence refuses the container — §9.3.1 MA-84: a value a
# certificate was revoked by is not weighed against anything, and it is not the
# verifier's own revocation input that says so but the seal's
seal_ltv 65-ltv-carried-revocation \
	META-INF/ltv/crl-intermediateA-revoked.pem=$ltv/crl-intermediateA-revoked.pem \
	META-INF/ltv/crl-intermediateA-revoked.pem.tst=$ltv/crl-intermediateA-revoked.pem.tst \
	META-INF/ltv/crl-rootA-clean.pem=$ltv/crl-rootA-clean.pem \
	META-INF/ltv/crl-rootA-clean.pem.tst=$ltv/crl-rootA-clean.pem.tst

# every assertion survived the rebuild, byte for byte

after=$(mktemp "${TMPDIR:-/tmp}/mkp3.after.XXXXXX")
for v in $vectors; do
	[ -f "vectors/$v/expected.txt" ] || {
		printf 'mkp3.sh: vectors/%s/expected.txt is MISSING after the rebuild — the rebuild destroyed an\n' "$v" >&2
		printf '         assertion and the tree would look green while asserting nothing. Aborting.\n' >&2
		rm -f "$after"
		exit 1
	}
	sha256sum "vectors/$v/expected.txt" >>"$after"
done
if ! cmp -s "$guard" "$after"; then
	printf 'mkp3.sh: an expected.txt CHANGED during the rebuild — a rebuild never rewrites an assertion:\n' >&2
	diff "$guard" "$after" >&2 || true
	rm -f "$after"
	exit 1
fi
rm -f "$after"

printf 'mkp3.sh: rebuilt the P3 vectors under %s/vectors (%d expected.txt byte-identical)\n' \
	"$repo" "$(wc -l <"$guard")"
