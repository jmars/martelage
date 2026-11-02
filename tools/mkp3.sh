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
mkpkg() { # $1: dir, $2: claim timestamp ("qualified"|"none"), $3: container reference
	python3 - "$1" "$2" "$3" <<'PY'
import json, os, sys
out, ts, ref = sys.argv[1], sys.argv[2], sys.argv[3]
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
        "ltv": False,
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

# remove the GENERATED parts only: the package directories and the containers.
# expected.txt is hand-written and is never touched by a rebuild.
for v in 34-seal-verified 35-seal-digest-moved 36-anchor-untrusted 37-self-seal \
         38-no-timestamp 39-container-malformed 40-signer-expired 41-signature-broken \
         42-multisigner-operator 43-ca-signer 44-chain-expired 45-tsa-expired \
         46-zip-duplicate 47-manifest-path-escape; do
	rm -rf "vectors/$v/pkg" "vectors/$v/pkg-moved"
	rm -f "vectors/$v"/*.asice
done

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

printf 'mkp3.sh: rebuilt the P3 vectors under %s/vectors\n' "$repo"
