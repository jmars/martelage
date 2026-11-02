#!/bin/sh
# run.sh — the one command that runs vector 66, every arm of it.
#
#   sh vectors/66-fetch-local/run.sh        # from anywhere; paths resolve to the repo
#
# This vector is about a FETCHER, so unlike every other vector it has to move
# bytes over a network before the verifier can read them. The rig
# (tools/revmirror.py) is loopback test tooling: it binds 127.0.0.1:18437 and
# nothing else. This script starts it, runs every arm against it, and STOPS it —
# three rigs total, one per TLS configuration, each stopped before the next
# starts. Each rig also carries --exit-after as a backstop: if this script dies,
# the rig still leaves. The script refuses to start if 18437 is already
# listening — a rig left running is a fault, not a convenience (a second suite
# run must not silently fetch from a rig it did not start) — and asserts the
# port free again before it reports success.
#
# Every arm's command is printed verbatim before it runs, so any single arm can
# be re-run by hand from this transcript. An arm passes only when BOTH its exit
# code and every must-print literal match what vectors/66-fetch-local/expected.txt
# documents; the script's own exit is 0 only when every arm matched.
#
# Scratch (the fetched material, its provenance records) lives in one mktemp -d
# directory and is removed at the end. The repo tree is written by nothing here.

set -u
LC_ALL=C
export LC_ALL

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"

PORT=18437
RIG=tools/revmirror.py
SCRATCH=$(mktemp -d "${TMPDIR:-/tmp}/p3-fetch-vector66.XXXXXX")
FAILS=0
ARMS=0
PIDS=""

cleanup() {
    for pid in $PIDS; do
        kill "$pid" 2>/dev/null && wait "$pid" 2>/dev/null
    done
    rm -rf "$SCRATCH"
}
trap cleanup EXIT INT TERM

port_free() {
    python3 - "$1" <<'PY'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

# start_rig ARGS... — start the rig, wait until it answers, remember its pid.
start_rig() {
    port_free "$PORT" || {
        echo "FATAL: port $PORT is already listening — a rig (or something else)" >&2
        echo "is already on the vector's port. Stop it and re-run; this suite will" >&2
        echo "not share a port with a process it did not start." >&2
        exit 2
    }
    python3 "$RIG" --port "$PORT" --exit-after 300 "$@" &
    RIG_PID=$!
    PIDS="$PIDS $RIG_PID"
    i=0
    while [ "$i" -lt 30 ]; do
        if port_free "$PORT"; then
            : # not accepting yet
        else
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done
    echo "FATAL: the rig did not start listening on $PORT within 30s" >&2
    exit 2
}

stop_rig() {
    kill "$RIG_PID" 2>/dev/null
    wait "$RIG_PID" 2>/dev/null
    PIDS=${PIDS% *}
    i=0
    while [ "$i" -lt 10 ]; do
        if port_free "$PORT"; then
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done
    echo "FATAL: port $PORT still listening 10s after the rig was stopped" >&2
    exit 2
}

# arm NAME EXPECTED_EXIT OUTDIR MUST_BE_EMPTY(0/1) LITERAL... — run the command
# already recorded in $CMD, check its exit code, its must-print literals and,
# when asked, that nothing was written.
arm() {
    name=$1; want=$2; outdir=$3; empty=$4; shift 4
    ARMS=$((ARMS + 1))
    log="$SCRATCH/$name.out"
    echo "── arm $name:"
    echo "   \$ $CMD"
    sh -c "$CMD" >"$log" 2>&1
    got=$?
    ok=1
    [ "$got" -eq "$want" ] || { echo "   FAIL $name: exit $got, expected $want"; ok=0; }
    for lit in "$@"; do
        if grep -qF -- "$lit" "$log"; then
            echo "   ok   $name: \"$lit\""
        else
            echo "   FAIL $name: must-print line absent: \"$lit\""
            ok=0
        fi
    done
    if [ "$empty" = "1" ]; then
        n=$(find "$outdir" -type f 2>/dev/null | wc -l | tr -d ' ')
        if [ "$n" = "0" ]; then
            echo "   ok   $name: nothing written (0 files in $outdir)"
        else
            echo "   FAIL $name: expected an empty output directory, found $n file(s)"
            ok=0
        fi
    fi
    [ "$ok" = "1" ] || FAILS=$((FAILS + 1))
}

fetch_cmd() {
    CMD="tools/p3-fetch --out '$1' ${2:-} 2>&1"
}

verify_cmd() {
    CMD="$1 2>&1"
}

echo "vector 66-fetch-local — the fetcher and the pair, offline over loopback"
echo "scratch: $SCRATCH"
echo

# ══ rig 1: plain HTTP, every adversarial arm mounted at once ════════════════
start_rig --ocsp \
    --trylater /trylater \
    --map /err6=vectors/66-fetch-local/responder-error-unauthorized.der \
    --redirect /tofile=file:///etc/hostname \
    --redirect /loop=http://127.0.0.1:18437/loop \
    --fill /big=25000000

# Arms 1a–1c: the fetch. signerA-fetch's AIA names the OCSP URL, its CRLDP the
# CRL URL; rootA's CRL is fetched by explicit URL because no certificate in the
# chain names it (rootA is the anchor). All three land in ONE directory.
PAIR="$SCRATCH/fetched"

fetch_cmd "$PAIR" "--kind ocsp --cert vectors/pki/signerA-fetch.crt.pem --issuer vectors/pki/intermediateA.crt.pem"
arm 1a-fetch-ocsp-nonce-matched 0 "$PAIR" 0 \
    "asked: 1 item(s)" \
    "POST 200 http://127.0.0.1:18437/ocsp" \
    "nonce: matched" \
    "wrote $PAIR/ocsp-0A11-" \
    "exit: 0"
cp "$PAIR.fetch.json" "$SCRATCH/record-1a.json"   # each run writes its own record

fetch_cmd "$PAIR" "--kind crl --cert vectors/pki/signerA-fetch.crt.pem"
arm 1b-fetch-crl-from-CDP 0 "$PAIR" 0 \
    "asked: 1 item(s)" \
    "GET 200 http://127.0.0.1:18437/crl" \
    "parsed CRL (PEM)" \
    "wrote $PAIR/crl-martelage-test-intermediate-A-" \
    "exit: 0"
cp "$PAIR.fetch.json" "$SCRATCH/record-1b.json"

fetch_cmd "$PAIR" "--url http://127.0.0.1:18437/crl-rootA-clean.pem --kind crl"
arm 1c-fetch-rootA-crl 0 "$PAIR" 0 \
    "asked: 1 item(s)" \
    "wrote $PAIR/crl-martelage-test-root-A-" \
    "exit: 0"
cp "$PAIR.fetch.json" "$SCRATCH/record-1c.json"

# Arm 2: THE PAIR — the fetched directory handed to the real, offline verifier.
# Every check is re-made by the verifier: this line of its report says the
# material is read from disk like any supplied input (MA-85: the fetch added
# bytes, not confidence), and the verdict names the fetched files.
verify_cmd "validator/p3-verify --container vectors/58-revocation-dir-garbage/seal.asice --trust-anchors vectors/pki/anchors --operator-cert vectors/pki/operator.crt.pem --revocation-dir '$PAIR' vectors/58-revocation-dir-garbage/pkg"
arm 2-pair-verify-conformant 0 "$PAIR" 0 \
    "read from disk, offline: nothing is fetched" \
    "usable CRL (PEM)" \
    "usable OCSP response (DER)" \
    "checked and clean, from" \
    "checked CLEAN" \
    "verdict      CONFORMANT"

# Arm 2b: the LTV boundary (MA-84) — the SAME fetched directory, full of usable
# material, cannot satisfy an ltv:true claim: that claim asserts material the
# container CARRIES, so vector 60's container is still refused with the fetched
# bytes sitting in --revocation-dir.
verify_cmd "validator/p3-verify --container vectors/60-ltv-absent/seal.asice --trust-anchors vectors/pki/anchors --operator-cert vectors/pki/operator.crt.pem --revocation-dir '$PAIR' vectors/60-ltv-absent/pkg"
arm 2b-fetched-material-never-ltv 1 "$PAIR" 0 \
    "p3.7     long-term validation REFUSED — ltv=true with no carried material" \
    "the evidence contradicts the claim it was supposed to carry" \
    "verdict      NON-CONFORMANT"

# Arms 3–7: refusals. Each is ONE item, so each refusal is the whole run: exit 2
# (nothing fetched at all), nothing written, the refusal named.
fetch_cmd "$SCRATCH/arm3-delta" "--url http://127.0.0.1:18437/crl-intermediateA-delta.pem --kind crl"
arm 3-delta-crl-refused 2 "$SCRATCH/arm3-delta" 1 \
    "REFUSED: it is a DELTA CRL (X509v3 Delta CRL Indicator present)"

fetch_cmd "$SCRATCH/arm4-trylater" "--url http://127.0.0.1:18437/trylater"
arm 4-trylater-refused-by-name 2 "$SCRATCH/arm4-trylater" 1 \
    "REFUSED: the responder answered 'trylater (3)'"

fetch_cmd "$SCRATCH/arm4b-err6" "--url http://127.0.0.1:18437/err6"
arm 4b-unauthorized-refused-by-name 2 "$SCRATCH/arm4b-err6" 1 \
    "REFUSED: the responder answered 'unauthorized (6)'"

fetch_cmd "$SCRATCH/arm5-tofile" "--url http://127.0.0.1:18437/tofile --kind crl"
arm 5a-file-scheme-refused 2 "$SCRATCH/arm5-tofile" 1 \
    "REFUSED: refusing scheme 'file' — only http and https are fetched"

fetch_cmd "$SCRATCH/arm5-loop" "--url http://127.0.0.1:18437/loop --kind crl"
arm 5b-redirect-cap 2 "$SCRATCH/arm5-loop" 1 \
    "REFUSED: redirect cap (--redirects 3) exceeded"

fetch_cmd "$SCRATCH/arm6-big" "--url http://127.0.0.1:18437/big --kind crl"
arm 6-max-bytes-before-write 2 "$SCRATCH/arm6-big" 1 \
    "REFUSED: the response body exceeded --max-bytes (20971520): aborted before anything was written"

stop_rig

# ══ rig 2: TLS with the rig certificate the anchors trust ═══════════════════
start_rig --https vectors/pki/mirror.crt.pem vectors/pki/mirror.key.pem

fetch_cmd "$SCRATCH/arm7-tls-good" "--url https://127.0.0.1:18437/crl --kind crl --tls-ca-dir vectors/pki/anchors"
arm 7a-tls-trusted-accepted 0 "$SCRATCH/arm7-tls-good" 0 \
    "tls peer: sha256 " \
    "exit: 0"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["requests"][0]["tls"]["peer_cert_sha256"]' "$SCRATCH/arm7-tls-good.fetch.json" >/dev/null 2>&1 || {
    echo "   FAIL 7a: the provenance record carries no tls.peer_cert_sha256"
    FAILS=$((FAILS + 1))
}

stop_rig

# ══ rig 3: TLS with the rootB certificate nothing here trusts ═══════════════
start_rig --https vectors/pki/mirror-bad.crt.pem vectors/pki/mirror-bad.key.pem

fetch_cmd "$SCRATCH/arm7b-tls-bad" "--url https://127.0.0.1:18437/crl --kind crl --tls-ca-dir vectors/pki/anchors"
arm 7b-tls-untrusted-refused 2 "$SCRATCH/arm7b-tls-bad" 1 \
    "REFUSED: TLS peer certificate is not trusted under vectors/pki/anchors"

stop_rig

# ══ the anti-linger proof ═══════════════════════════════════════════════════
if port_free "$PORT"; then
    echo
    echo "ok: port $PORT is free — no rig was left behind"
else
    echo
    echo "FAIL: port $PORT is still listening after all three rigs were stopped"
    FAILS=$((FAILS + 1))
fi

echo
echo "arms: $ARMS, failed: $FAILS"
if [ "$FAILS" -eq 0 ]; then
    echo "vector 66-fetch-local: every arm matched its documented exit code and must-print lines"
    exit 0
fi
echo "vector 66-fetch-local: $FAILS arm(s) did NOT match — see the FAIL lines above"
exit 1
