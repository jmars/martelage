#!/bin/sh
# mklv.sh — the ARCHIVAL TIMESTAMPS the long-term-validation vectors carry.
#
# Long-term validation needs, for each validation value, an RFC 3161 timestamp
# whose signature covers that value's bytes: the timestamp is what fixes the
# moment at which the value was already true, and it is the only thing that can
# say a CRL's window still had not closed at the moment the value was archived.
# Those timestamps are built here, over the CRL files the revocation vectors hand
# to the verifier, and tools/mkasic.py carries them into a container as
# `META-INF/ltv/...` entries under the seal (--manifest-entry).
#
# THROWAWAY TEST MATERIAL. The TSA is vectors/pki/tsa.crt.pem, built by
# tools/mkpki.sh, and nothing here is trusted by anyone.
#
# Runnable offline. Needs only the `openssl` binary: `openssl ts -query` builds
# the request file and `openssl ts -reply -queryfile` answers it. No responder is
# contacted, no port is opened and no URL is read — the reply is a local signing
# operation, exactly as in tools/mkasic.py.
#
#   sh tools/mklv.sh                  # rebuild vectors/pki/ltv
#   sh tools/mklv.sh /some/other/pki  # another PKI built by tools/mkpki.sh
#
# WHY THESE ARE NOT RE-DATED (unlike tools/mkocsp.sh's responses). An OCSP
# response is re-dated by rewriting its DER window and re-signing the
# tbsResponseData with `openssl dgst -sign`; an RFC 3161 token's time lives
# inside a CMS SignedAttributes structure that `openssl ts` will not let you fix
# from the command line. So the genTime of these tokens is the build second, and
# what each arm asserts is relative to it:
#   * a CRL whose nextUpdate is 2099 is inside its window at any build second;
#   * a CRL whose nextUpdate is 2021 is OUTSIDE its window at any build second
#     after 2021, which is the arm that must be refused.
# That is a documented time dependency of the same kind the expired CRLs already
# have (they are compared to `now` in the other arms); the direction of the
# inequality is fixed by the fixture dates, not by the day it was built.

set -eu
LC_ALL=C
export LC_ALL

here=$(cd -- "$(dirname -- "$0")" && pwd)
repo=$(cd -- "$here/.." && pwd)

pki=${1:-$repo/vectors/pki}
[ -d "$pki" ] || { printf 'mklv.sh: %s is not a directory\n' "$pki" >&2; exit 1; }
pki=$(cd -- "$pki" && pwd)

OPENSSL=${OPENSSL:-openssl}
command -v "$OPENSSL" >/dev/null 2>&1 || { printf 'mklv.sh: no %s on PATH\n' "$OPENSSL" >&2; exit 1; }

for f in tsa.crt.pem tsa.key.pem tsa.cnf rootA.crt.pem ocsp-signerA-good.der \
         crl-intermediateA-clean.pem crl-rootA-clean.pem crl-intermediateA-expired.pem \
         crl-intermediateA-revoked.pem; do
	[ -f "$pki/$f" ] || {
		printf 'mklv.sh: %s/%s missing — run tools/mkpki.sh first\n' "$pki" "$f" >&2
		exit 1
	}
done

out=$pki/ltv
rm -rf "$out"
mkdir -p "$out"

# the evidence files, byte for byte as the revocation arms ship them, so an arm
# that carries a CRL into a container carries the same bytes it would hand over
# with --revocation
for f in crl-intermediateA-clean.pem crl-rootA-clean.pem crl-intermediateA-expired.pem \
         crl-intermediateA-revoked.pem ocsp-signerA-good.der; do
	cp "$pki/$f" "$out/$f"
done

# one archival timestamp per evidence file, over that file's exact bytes.
# `openssl ts -reply` resolves the TSA config's relative paths against the
# working directory, so the reply runs with the PKI directory as its cwd.
for f in crl-intermediateA-clean.pem crl-rootA-clean.pem crl-intermediateA-expired.pem \
         crl-intermediateA-revoked.pem ocsp-signerA-good.der; do
	"$OPENSSL" ts -query -data "$out/$f" -sha256 -cert -out "$out/$f.tsq" 2>/dev/null
	(cd "$pki" && "$OPENSSL" ts -reply -config "$pki/tsa.cnf" \
		-queryfile "$out/$f.tsq" -out "$out/$f.tst" 2>/dev/null)
	rm -f "$out/$f.tsq"
	"$OPENSSL" ts -verify -in "$out/$f.tst" -data "$out/$f" \
		-CAfile "$pki/anchors/rootA.crt.pem" -no_check_time >/dev/null 2>&1 || {
		printf 'mklv.sh: the token built over %s does not verify against root A\n' "$f" >&2
		exit 1
	}
done

chmod 644 "$out"/*

printf 'mklv.sh: built the archival timestamps under %s\n' "$out"
for f in crl-intermediateA-clean.pem crl-rootA-clean.pem crl-intermediateA-expired.pem \
         crl-intermediateA-revoked.pem ocsp-signerA-good.der; do
	printf '  %-32s %s\n' "$f.tst" \
		"$("$OPENSSL" ts -reply -in "$out/$f.tst" -text 2>/dev/null |
			grep -E '^Time stamp|^Serial number' | tr '\n' ' ' | sed 's/  */ /g')"
done
