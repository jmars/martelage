#!/usr/bin/env python3
"""revmirror — the loopback rig the revocation-fetch arms run against.

ONE process, ONE socket, bound to 127.0.0.1:18437 and to nothing else. A bind
to any other address is REFUSED before the socket exists: this is test
tooling for tools/p3-fetch, and a rig that listens on 0.0.0.0 is a service.
It serves bytes and decides nothing — it is not a responder implementation but
the test double for one: its live OCSP arm shells out to the SAME
`openssl ocsp -index` invocation tools/mkocsp.sh uses, so a live answer has the
shipped fixtures' shape and ECHOES the request nonce (MEASURED: openssl's
responder copies the request nonce unless told not to).

It must not linger: pass --exit-after SECONDS and it stops itself, or stop it
with SIGTERM/SIGINT (or `kill PID`); every arm below is startable, exercisable
and stopped in one documented command. python3 stdlib only.

THE ARMS — one documented command each (run from the repo root):

  static material at the paths AIA/CRLDP name (the zero-flag mode):
    python3 tools/revmirror.py --exit-after 120
      /crl  -> vectors/pki/crl-intermediateA-clean.pem (the CRLDP fixture)
      /ocsp -> vectors/pki/ocsp-signerA-good.der      (the AIA fixture)
      plus any vectors/pki file by basename: /crl-rootA-clean.pem, ...
      (private keys are never served by the basename map; use --map to hand
      out a specific file — everything here is throwaway anyway)

  live OCSP responder (nonce echoed; --cert mode's POST lands here):
    python3 tools/revmirror.py --ocsp --exit-after 120
      default index: good for serial 0A11 under intermediate A, the same line
      tools/mkocsp.sh writes. --ocsp-index FILE replaces it (format: the
      openssl ca index, one line, as tools/mkocsp.sh's index() writes it).

  404 (the default for every path no arm claims):
    python3 tools/revmirror.py --exit-after 120
      then fetch http://127.0.0.1:18437/anything-unclaimed

  302 to a file: URL (refused by name, never followed):
    python3 tools/revmirror.py --redirect /crl=file:///etc/hostname --exit-after 120

  cross-host 302 that is meant to be FOLLOWED (host label changes, the
  connection stays on loopback — localhost falls back from ::1 to 127.0.0.1):
    python3 tools/revmirror.py --redirect /crl=http://localhost:18437/crl2 \
        --map /crl2=vectors/pki/crl-intermediateA-clean.pem --exit-after 120

  a hop chain past --redirects (this one loops to itself; the fetcher must
  refuse at its cap, not follow forever):
    python3 tools/revmirror.py --redirect /crl=http://127.0.0.1:18437/crl --exit-after 120

  an oversized body (truthful Content-Length, 25 MB against the 20 MB cap):
    python3 tools/revmirror.py --fill /crl=25000000 --exit-after 120

  a stalled body (200, a large Content-Length, then not one byte):
    python3 tools/revmirror.py --stall /crl --exit-after 120

  a 5-byte DER `tryLater` OCSP response (30 03 0A 01 03):
    python3 tools/revmirror.py --trylater /ocsp --exit-after 120

  HTTPS with the mirror certificate the anchors trust (mirror.crt.pem is
  issued by root A, SAN IP:127.0.0.1 — see vectors/pki/README.md):
    python3 tools/revmirror.py --https vectors/pki/mirror.crt.pem \
        vectors/pki/mirror.key.pem --exit-after 120
    fetch with --tls-ca-dir vectors/pki/anchors

  HTTPS with the UNTRUSTED mirror certificate (mirror-bad.crt.pem: the same
  subject and SAN, issued by root B, which anchors/ withholds):
    python3 tools/revmirror.py --https vectors/pki/mirror-bad.crt.pem \
        vectors/pki/mirror-bad.key.pem --exit-after 120

First arm registered at a path wins; later flags do not override earlier ones.
"""

import argparse
import ipaddress
import os
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROG = "revmirror"
DEFAULT_BIND = "127.0.0.1"     # the ONLY address this rig may listen on
DEFAULT_PORT = 18437           # the port vectors/pki's AIA and CRLDP name
TRYLATER_DER = bytes.fromhex("30030a0103")   # SEQUENCE { ENUMERATED 3 } — tryLater
REQUEST_CAP = 1 * 1024 * 1024  # the rig reads request bodies no larger than this
STALL_HOLD = 120.0             # seconds a stalled arm holds the socket open


def log(msg):
    sys.stderr.write("%s: %s\n" % (PROG, msg))
    sys.stderr.flush()


class Rig:
    """the route table: what answers at which path, in registration order."""

    def __init__(self, args):
        self.args = args
        self.pki = args.pki
        self.routes = []          # (path, kind, arg) — first match wins
        for spec in args.map or []:
            path, _, fname = spec.partition("=")
            self.routes.append((self.path_of(path, "--map"), "map", fname))
        for spec in args.redirect or []:
            path, _, url = spec.partition("=")
            self.routes.append((self.path_of(path, "--redirect"), "redirect", url))
        for spec in args.fill or []:
            path, _, count = spec.partition("=")
            self.routes.append((self.path_of(path, "--fill"), "fill", int(count)))
        for path in args.stall or []:
            self.routes.append((self.path_of(path, "--stall"), "stall", None))
        for path in args.trylater or []:
            self.routes.append((self.path_of(path, "--trylater"), "trylater", None))
        if args.ocsp:
            self.routes.append((self.path_of(args.ocsp, "--ocsp"), "ocsp", None))
        self.ocsp_index = args.ocsp_index
        self.stopped = threading.Event()
        self.stop_reason = "exit"   # named by whichever stop path fires

    @staticmethod
    def path_of(path, flag):
        if not path.startswith("/"):
            raise SystemExit("%s: %s paths start with '/': %s" % (PROG, flag, path))
        return path

    def match(self, path):
        for rpath, kind, arg in self.routes:
            if rpath == path:
                return kind, arg
        return None, None

    def static_file(self, path):
        """the zero-flag mode: a vectors/pki file by basename, or the AIA/CRLDP
        defaults. Returns (filename, content_type) or (None, None)."""
        name = urllib.parse.unquote(path.lstrip("/"))
        if not name or not all(c.isalnum() or c in "._-" for c in name):
            return None, None
        if name.endswith(".key.pem"):
            return None, None   # keys are committed but no arm needs them served
        candidates = {
            "crl": ("crl-intermediateA-clean.pem", "application/pkix-crl"),
            "ocsp": ("ocsp-signerA-good.der", "application/ocsp-response"),
        }.get(name)
        if candidates:
            return os.path.join(self.pki, candidates[0]), candidates[1]
        fname = os.path.join(self.pki, name)
        if os.path.isfile(os.path.join(self.pki, name)):
            ctype = "application/pkix-crl" if name.startswith("crl-") else (
                "application/ocsp-response" if name.startswith("ocsp-") else
                "application/octet-stream")
            return fname, ctype
        return None, None


def build_default_index(pki, workdir):
    """the index line tools/mkocsp.sh's index() writes for signerA: status V,
    the fixed expiry, serial 0A11, the subject EXACTLY as the certificate
    states it (commas escaped the way openssl's index reader wants)."""
    out = subprocess.run(
        ["openssl", "x509", "-in", os.path.join(pki, "signerA.crt.pem"),
         "-noout", "-subject", "-nameopt", "oneline,-space_eq"],
        capture_output=True)
    if out.returncode != 0:
        raise SystemExit("%s: cannot read %s/signerA.crt.pem: %s"
                         % (PROG, pki, out.stderr.decode().strip()))
    subject = out.stdout.decode().strip().removeprefix("subject=").replace(", ", "\\, ")
    path = os.path.join(workdir, "index-good.txt")
    with open(path, "w") as fh:
        fh.write("V\t20990101000000Z\t\t0A11\tunknown\t%s\n" % subject)
    return path


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # every answer frames itself with a length
    server_version = PROG
    rig = None                      # set in main()

    def log_message(self, fmt, *args):
        log("%s %s" % (self.address_string(), fmt % args))

    def _reply(self, status, body, ctype="text/plain; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self._write(body)

    def _write(self, body):
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            self.connection.close()   # the client hung up; that is its right

    # ── GET ────────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.rig.match(self.path) == ("ocsp", None):
            self._reply(405, b"rig: the OCSP arm answers POST, not GET\n")
            return
        self._serve()

    # ── POST: the live OCSP arm — and, for every other arm, the same answer
    # GET would get. A --kind ocsp fetch POSTs, and the arms it may be pointed
    # at (tryLater, a static fixture) model responders: a responder answers
    # what it answers regardless of the method the question arrived by.
    def do_POST(self):
        rig = self.rig
        kind, _ = rig.match(self.path)
        if kind == "ocsp":
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= REQUEST_CAP:
                self._reply(400, ("rig: request body must be 1..%d bytes, got %r\n"
                                  % (REQUEST_CAP, length)).encode())
                return
            req = os.path.join(rig.workdir, "request-%d.der" % threading.get_ident())
            with open(req, "wb") as fh:
                fh.write(self.rfile.read(length))
            resp = req + ".resp"
            # the SAME invocation tools/mkocsp.sh's respond() uses — including
            # -ndays 3000 — with the request taken from the POSTed body instead of
            # a file built offline. openssl's responder echoes the request nonce
            # (MEASURED), which is the whole point of this arm.
            proc = subprocess.run(
                ["openssl", "ocsp",
                 "-index", rig.ocsp_index,
                 "-rsigner", os.path.join(rig.pki, "ocsp-responder.crt.pem"),
                 "-rkey", os.path.join(rig.pki, "ocsp-responder.key.pem"),
                 "-CA", os.path.join(rig.pki, "intermediateA.crt.pem"),
                 "-reqin", req, "-respout", resp, "-ndays", "3000"],
                capture_output=True)
            if proc.returncode != 0 or not os.path.exists(resp):
                detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
                log("openssl ocsp failed (%d): %s" % (proc.returncode,
                                                      detail[0] if detail else "no output"))
                self._reply(500, b"rig: the responder could not answer this request\n")
                return
            with open(resp, "rb") as fh:
                self._reply(200, fh.read(), ctype="application/ocsp-response")
            return
        self._serve()

    # ── everything except the live responder, for either method ────────────
    def _serve(self):
        rig = self.rig
        kind, arg = rig.match(self.path)
        if kind == "redirect":
            # the adversarial arm: answer with the Location and nothing else.
            # Whether to follow it, and where it may point, is the FETCHER's
            # policy — the rig hands out whatever URL it was told to.
            self._reply(302, b"", extra={"Location": arg})
            return
        if kind == "fill":
            # truthful Content-Length, then that many bytes: the fetcher's
            # --max-bytes is what must stop this, not a lie in the header
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(arg))
            self.end_headers()
            chunk = b"\x00" * 65536
            remaining = arg
            try:
                while remaining > 0 and not rig.stopped.is_set():
                    piece = chunk[:min(len(chunk), remaining)]
                    self.wfile.write(piece)
                    self.wfile.flush()
                    remaining -= len(piece)
            except (BrokenPipeError, ConnectionResetError):
                pass   # the fetcher hit its cap and closed: the arm worked
            return
        if kind == "stall":
            # 200, a large Content-Length, and then NOT ONE BYTE, with the
            # socket held open — a truncated body would be a different
            # refusal; the fetcher must be the one that gives up, on its
            # --timeout, while no byte arrives
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(64 * 1024 * 1024))
            self.end_headers()
            deadline = time.monotonic() + STALL_HOLD
            while time.monotonic() < deadline and not rig.stopped.is_set():
                time.sleep(0.2)
            return
        if kind == "trylater":
            self._reply(200, TRYLATER_DER, ctype="application/ocsp-response")
            return
        if kind == "map":
            try:
                with open(arg, "rb") as fh:
                    self._reply(200, fh.read(), ctype="application/octet-stream")
            except OSError as exc:
                self._reply(500, ("rig: --map source unreadable: %s\n" % exc).encode())
            return
        fname, ctype = rig.static_file(self.path)
        if fname:
            with open(fname, "rb") as fh:
                self._reply(200, fh.read(), ctype=ctype)
            return
        self._reply(404, b"rig: nothing is served at this path (the 404 arm)\n")


def check_bind(address):
    """127.0.0.1 or nothing. This rig exists to give tools/p3-fetch a loopback
    to talk to; the same binary pointed at any other interface is a network
    service, and this repository does not build one."""
    ip = ipaddress.ip_address(address)   # raises ValueError on nonsense
    if ip != ipaddress.ip_address(DEFAULT_BIND):
        raise SystemExit(
            "%s: refusing to bind %s — this rig serves the loopback fetch arms "
            "and NOTHING else; bound to any other address (0.0.0.0, a LAN "
            "address, ::1) it would be a network service, which is exactly "
            "what it must not be" % (PROG, address))


def stop_gracefully(server, reason):
    """shutdown() from a thread of its own: called from a signal handler it
    would deadlock (the handler runs in the thread serve_forever occupies)."""
    Handler.rig.stop_reason = reason
    threading.Thread(target=server.shutdown, daemon=True).start()


def main(argv=None):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(
        prog=PROG, description=__doc__.split("\n\n")[1] if "\n\n" in __doc__ else __doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Every arm is documented with its one-command invocation in the "
               "module docstring. Stop with --exit-after, SIGINT, or SIGTERM; "
               "a rig left running is a fault, not a convenience.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, metavar="N",
                    help="port to listen on (default %d, the port vectors/pki's "
                         "AIA and CRLDP name)" % DEFAULT_PORT)
    ap.add_argument("--bind", default=DEFAULT_BIND, metavar="IP",
                    help="refused unless it is exactly %s (default): this rig is "
                         "loopback test tooling, and on any other interface it "
                         "would be a network service" % DEFAULT_BIND)
    ap.add_argument("--pki", default=os.path.join(repo, "vectors", "pki"), metavar="DIR",
                    help="the fixture directory served by the static map "
                         "(default vectors/pki)")
    ap.add_argument("--exit-after", type=float, default=None, metavar="SECONDS",
                    help="stop SECONDS after start (the anti-linger default for "
                         "unattended runs; without it the rig runs until "
                         "SIGINT/SIGTERM)")
    ap.add_argument("--map", action="append", metavar="PATH=FILE",
                    help="serve FILE's bytes at PATH (repeatable)")
    ap.add_argument("--ocsp", nargs="?", const="/ocsp", metavar="PATH",
                    help="answer POSTs at PATH (default /ocsp) with a live "
                         "`openssl ocsp -index` response — the same invocation "
                         "tools/mkocsp.sh uses, so the nonce is echoed")
    ap.add_argument("--ocsp-index", metavar="FILE",
                    help="the CA index the live responder reads (default: a "
                         "good-for-signerA index written at startup)")
    ap.add_argument("--redirect", action="append", metavar="PATH=URL",
                    help="answer GET PATH with 302 and Location: URL — used for "
                         "the file:// refusal, the cross-host hop and the "
                         "past-the-cap chain (repeatable)")
    ap.add_argument("--fill", action="append", metavar="PATH=N",
                    help="serve N bytes at PATH with a truthful Content-Length: "
                         "the oversized-body arm (repeatable)")
    ap.add_argument("--stall", action="append", metavar="PATH",
                    help="serve PATH with a large Content-Length and no body "
                         "bytes, socket held open: the stalled-body arm "
                         "(repeatable)")
    ap.add_argument("--trylater", action="append", metavar="PATH",
                    help="serve the 5-byte DER tryLater OCSP response at PATH "
                         "(repeatable)")
    ap.add_argument("--https", nargs=2, metavar=("CERT", "KEY"),
                    help="speak TLS with this certificate and key "
                         "(vectors/pki/mirror.crt.pem under anchors/; "
                         "vectors/pki/mirror-bad.crt.pem for the untrusted arm)")
    args = ap.parse_args(argv)

    check_bind(args.bind)
    for flag, values in (("--map", args.map), ("--redirect", args.redirect)):
        for spec in values or []:
            if spec.count("=") < 1:
                ap.error("%s wants PATH=VALUE, got %r" % (flag, spec))
    for spec in args.fill or []:
        if spec.count("=") < 1 or not spec.rpartition("=")[2].isdigit():
            ap.error("--fill wants PATH=BYTES, got %r" % spec)

    rig = Rig(args)
    workdir = tempfile.mkdtemp(prefix="revmirror.")
    rig.workdir = workdir
    if args.ocsp:
        for name in ("ocsp-responder.crt.pem", "ocsp-responder.key.pem",
                     "intermediateA.crt.pem", "signerA.crt.pem"):
            if not os.path.isfile(os.path.join(args.pki, name)):
                raise SystemExit("%s: --ocsp needs %s/%s — run tools/mkpki.sh first"
                                 % (PROG, args.pki, name))
        if not rig.ocsp_index:
            rig.ocsp_index = build_default_index(args.pki, workdir)

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.daemon_threads = True
    Handler.rig = rig
    if args.https:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(args.https[0], args.https[1])
        server.socket = ctx.wrap_socket(server.socket, server_side=True)

    if args.exit_after is not None:
        timer = threading.Timer(
            args.exit_after,
            lambda: stop_gracefully(server, "--exit-after %g elapsed" % args.exit_after))
        timer.daemon = True
        timer.start()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop_gracefully(server, "SIGINT/SIGTERM"))

    scheme = "https" if args.https else "http"
    log("serving on %s://%s:%d (pid %d)" % (scheme, args.bind, args.port, os.getpid()))
    for path, kind, arg in rig.routes:
        log("  %-28s %s %s" % (path, kind, arg if arg is not None else ""))
    if not rig.routes:
        log("  (static mode: /crl, /ocsp and any vectors/pki file by basename)")
    log("stop: wait --exit-after%s, or kill %d" %
        (" %g" % args.exit_after if args.exit_after is not None else " / SIGTERM", os.getpid()))
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        shutil.rmtree(workdir, ignore_errors=True)
    log("stopped (%s)" % rig.stop_reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
