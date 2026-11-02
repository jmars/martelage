#!/usr/bin/env python3
"""mkasic.py — build an ASiC-E container for the P3 vectors.

This is the PRODUCER side of the fixtures in vectors/34..40. It packs a
MARTELAGE package directory into a ZIP shaped like an ETSI EN 319 162-1
ASiC-E container:

    mimetype                     first entry, stored, application/vnd.etsi.asic-e+zip
    META-INF/manifest.xml        the ASiC manifest: one file-entry per covered
                                 file, each with its sha256
    META-INF/signatures.p7s      a detached CAdES (CMS SignedData, DER)
                                 signature over the exact bytes of manifest.xml
    META-INF/timestamp.tst       optional RFC 3161 token over the signature bytes
    <package files...>           the covered bytes

The construction this ships is the manifest-signature one: the signature covers
META-INF/manifest.xml, and the manifest carries the digests of the covered
files. That is a self-consistent ASiC-E shape and it is exactly what
validator/p3-verify checks; it is NOT the EN 319 162-1 multi-file concatenated
digest form, and p3-verify says so in its own report rather than pretending
otherwise.

Test material only. The keys come from vectors/pki, built by tools/mkpki.sh.

  python3 tools/mkasic.py --package vectors/01-minimal-conformant/pkg \
      --signer vectors/pki/signerA.crt.pem --key vectors/pki/signerA.key.pem \
      --chain vectors/pki/intermediateA.crt.pem \
      --timestamp --out vectors/34-seal-verified/seal.asice
"""

import argparse
import hashlib
import os
import subprocess
import sys
import warnings
import zipfile

MIMETYPE = "application/vnd.etsi.asic-e+zip"
MANIFEST = "META-INF/manifest.xml"
SIGNATURE = "META-INF/signatures.p7s"
TIMESTAMP = "META-INF/timestamp.tst"
NS = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"

MEDIA = {
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".md": "text/markdown",
    ".txt": "text/plain",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def package_files(pkg):
    """Every regular file in the package, relative to it, sorted."""
    out = []
    for root, dirs, names in os.walk(pkg):
        dirs.sort()
        for name in sorted(names):
            full = os.path.join(root, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            out.append(os.path.relpath(full, pkg))
    return sorted(out)


def build_manifest(pkg, files, skip, extra=()):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<manifest:manifest xmlns:manifest="%s" manifest:version="1.2">' % NS)
    lines.append(' <manifest:file-entry manifest:full-path="/" manifest:media-type="%s"/>' % MIMETYPE)
    for rel in files:
        if rel in skip:
            continue
        digest = sha256_file(os.path.join(pkg, rel))
        media = MEDIA.get(os.path.splitext(rel)[1], "application/octet-stream")
        lines.append(' <manifest:file-entry manifest:full-path="%s" manifest:media-type="%s">' % (rel, media))
        lines.append('  <manifest:digest manifest:digest-algorithm="sha256">%s</manifest:digest>' % digest)
        lines.append(' </manifest:file-entry>')
    for full, digest, _path in extra:
        lines.append(' <manifest:file-entry manifest:full-path="%s" manifest:media-type="application/octet-stream">'
                     % full)
        lines.append('  <manifest:digest manifest:digest-algorithm="sha256">%s</manifest:digest>' % digest)
        lines.append(' </manifest:file-entry>')
    lines.append('</manifest:manifest>')
    return ("\n".join(lines) + "\n").encode("utf-8")


def add(zf, name, data, stored=False):
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    zf.writestr(info, data)


def run(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write("mkasic.py: %s failed (%d)\n%s%s\n" % (" ".join(cmd), proc.returncode, proc.stdout, proc.stderr))
        sys.exit(1)
    return proc


def main(argv=None):
    ap = argparse.ArgumentParser(description="build an ASiC-E container for a martelage package")
    ap.add_argument("--package", required=True, help="the package directory to seal")
    ap.add_argument("--out", required=True, help="the container to write")
    ap.add_argument("--signer", required=True, help="signer certificate (PEM)")
    ap.add_argument("--key", required=True, help="signer private key (PEM)")
    ap.add_argument("--chain", default=None, help="intermediate certificate to carry in the signature (PEM)")
    ap.add_argument("--co-signer", action="append", default=[], metavar="CERT:KEY",
                    help="a SECOND signer of the same signature entry (repeatable). A second signerInfo is how a "
                         "co-signer escapes a verifier that reads only the first one")
    ap.add_argument("--tsa-config", default=None, help="the TSA configuration to stamp with (default: PKI/tsa.cnf)")
    ap.add_argument("--manifest-entry", action="append", default=[], metavar="PATH=FILE",
                    help="an extra ASiC manifest file-entry for PATH, with the digest of FILE, and a ZIP entry of "
                         "that name carrying FILE's bytes. PATH is used verbatim: no normalisation")
    ap.add_argument("--shadow-entry", action="append", default=[], metavar="NAME=FILE",
                    help="write a ZIP entry named NAME carrying FILE's bytes BEFORE the package files, so the "
                         "container holds two entries of that name with different bytes")
    ap.add_argument("--timestamp", action="store_true", help="add an RFC 3161 token over the signature")
    ap.add_argument("--pki", default=None, help="the test PKI directory (default: vectors/pki)")
    ap.add_argument("--break-mimetype", default=None, help="write this string as the mimetype instead of the correct one")
    ap.add_argument("--drop-entry", action="append", default=[], help="do not add this ZIP entry although the manifest lists it")
    ap.add_argument("--uncovered-entry", default=None, help="add this package file to the ZIP but NOT to the ASiC manifest")
    ap.add_argument("--mutate-manifest", action="store_true",
                    help="alter META-INF/manifest.xml AFTER signing it, leaving every stated digest intact: the "
                         "signature no longer covers the manifest and nothing else changed")
    args = ap.parse_args(argv)

    pkg = args.package
    if not os.path.isdir(pkg):
        sys.stderr.write("mkasic.py: %s is not a directory\n" % pkg)
        return 2
    pki = args.pki or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vectors", "pki")
    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    work = out + ".work"
    os.makedirs(work, exist_ok=True)

    files = package_files(pkg)
    if not files:
        sys.stderr.write("mkasic.py: %s holds no files\n" % pkg)
        return 2
    skip = set(args.uncovered_entry and [args.uncovered_entry] or [])
    extra_entries = []
    for item in args.manifest_entry:
        full, path = item.split("=", 1)
        extra_entries.append((full, sha256_file(path), path))
    manifest = build_manifest(pkg, files, skip, extra_entries)
    manifest_path = os.path.join(work, "manifest.xml")
    with open(manifest_path, "wb") as fh:
        fh.write(manifest)

    sig_path = os.path.join(work, "signatures.p7s")
    cmd = ["openssl", "cms", "-sign", "-binary", "-in", manifest_path,
           "-signer", args.signer, "-inkey", args.key, "-md", "sha256",
           "-outform", "DER", "-cades", "-out", sig_path]
    if args.chain:
        cmd += ["-certfile", args.chain]
    for pair in args.co_signer:
        cert, key = pair.split(":", 1)
        cmd += ["-signer", cert, "-inkey", key]
    run(cmd)

    ts_data = None
    if args.timestamp:
        ts_path = os.path.join(work, "timestamp.tst")
        query = os.path.join(work, "query.tsq")
        run(["openssl", "ts", "-query", "-data", os.path.abspath(sig_path), "-sha256", "-cert", "-out",
             os.path.abspath(query)])
        # openssl ts resolves the TSA config's relative paths against the cwd, so
        # the reply runs in the PKI directory and takes absolute paths itself
        run(["openssl", "ts", "-reply", "-config",
             os.path.abspath(args.tsa_config or os.path.join(pki, "tsa.cnf")),
             "-queryfile", os.path.abspath(query), "-out", os.path.abspath(ts_path)], cwd=pki)
        with open(ts_path, "rb") as fh:
            ts_data = fh.read()

    with open(sig_path, "rb") as fh:
        sig_data = fh.read()

    if args.mutate_manifest:
        # every stated digest stays exactly as signed; only the bytes the
        # signature covers move, so the only check that can catch it is the
        # signature check itself
        manifest = manifest.replace(b"</manifest:manifest>",
                                    b"<!-- added after the signature was made -->\n</manifest:manifest>")

    drop = set(args.drop_entry)
    shadows = [item.split("=", 1) for item in args.shadow_entry]
    if shadows:
        # a duplicate entry name is the point of that arm, not a mistake
        warnings.filterwarnings("ignore", message="Duplicate name.*")
    with zipfile.ZipFile(out, "w") as zf:
        add(zf, "mimetype", (args.break_mimetype or MIMETYPE).encode("utf-8"), stored=True)
        add(zf, MANIFEST, manifest)
        # a second entry of a name the manifest also covers, written FIRST: a
        # last-wins reader (zipfile.read) sees the covered copy, a first-wins
        # extractor writes these bytes, and nothing in the container says which
        for name, path in shadows:
            with open(path, "rb") as fh:
                add(zf, name, fh.read())
        for full, _digest, path in extra_entries:
            with open(path, "rb") as fh:
                add(zf, full, fh.read())
        for rel in files:
            if rel in drop:
                continue
            with open(os.path.join(pkg, rel), "rb") as fh:
                add(zf, rel, fh.read())
        add(zf, SIGNATURE, sig_data)
        if ts_data is not None:
            add(zf, TIMESTAMP, ts_data)

    # a ZIP holds no evidence of its own; keep the intermediate files out of
    # the tree so a vector directory is only the container and its text.
    for name in os.listdir(work):
        os.unlink(os.path.join(work, name))
    os.rmdir(work)

    print("%s  %s  (%d covered file(s)%s%s)" % (
        out, sha256_file(out), len(files) - len(skip),
        ", timestamped" if ts_data is not None else "",
        ", mimetype broken" if args.break_mimetype else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
