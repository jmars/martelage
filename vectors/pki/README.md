# The test PKI — THROWAWAY MATERIAL

> **Every key and every certificate in this directory is throwaway test material. None of it is
> secret, none of it is trusted by anything, and none of it may be used for any purpose whatsoever
> other than running the P3 vectors in this repository.** The private keys are committed on purpose:
> a vector that cannot be rebuilt from what is in the tree is not reproducible, and a vector whose
> keys were kept elsewhere would not be rebuildable by a reader. They are worth exactly nothing, and
> they are worthless *because* they are public — nothing here can sign anything that any real party
> would accept, and nothing here is a claim that anyone certifies anyone.

## What is here

| file | what it is |
|---|---|
| `openssl.cnf` | the extensions every certificate is issued with, and the config `mkpki.sh` reads |
| `rootA.crt.pem` / `rootA.key.pem` | test root A: the anchor the P3 vectors supply |
| `rootB.crt.pem` / `rootB.key.pem` | test root B: the anchor the vectors withhold until the arm that supplies it |
| `intermediateA.crt.pem` / `.key.pem` | an intermediate under root A, so the chain a verifier builds is not one hop |
| `intermediateA-expired.crt.pem` | the **same key and the same subject** as `intermediateA`, window `2020-01-01 .. 2021-01-01`: the chain-date arm, where the signer is valid and the certificate it chains through is not |
| `signerA.crt.pem` / `.key.pem` | **the sealer**: `CN=Witness AG` — a legal person other than the operator |
| `signerC.crt.pem` / `.key.pem` | a second sealer, `CN=Witness C GmbH`, under the same intermediate: the control for the two-signer arm, where neither signer is the operator |
| `signerB.crt.pem` / `.key.pem` | a sealer under root B, for the arm where no supplied anchor reaches the signer |
| `expired.crt.pem` / `.key.pem` | `CN=Retired Witness AG`, window `2020-01-01 .. 2021-01-01`: the date arm |
| `operator.crt.pem` / `.key.pem` | **the operator**: `CN=Operator GmbH`. Its key is what a self-seal uses, and what the co-signer arm adds behind a valid signer |
| `tsa.crt.pem` / `.key.pem` | the timestamping authority, `CN=martelage test TSA`, `EKU critical timeStamping` |
| `tsa-expired.crt.pem` | the **same key and subject** as `tsa`, window `2020-01-01 .. 2021-01-01`: a token from a TSA that was not valid when it stamped |
| `tsa.cnf`, `tsa.serial` | the TSA's configuration; `openssl ts -reply` reads the serial from here |
| `tsa-expired.cnf`, `tsa-expired.serial` | the same configuration pointing at `tsa-expired.crt.pem`: one certificate and one serial file different |
| `ocsp-responder.crt.pem` / `.key.pem` | the **delegated OCSP responder**, `CN=martelage test OCSP responder`, issued by intermediate A with `extendedKeyUsage = critical,OCSPSigning` — so its answers are authorised by the CA that issued the certificates it answers about, and its chain reaches root A |
| `ocsp-rogue.crt.pem` / `.key.pem` | a **self-signed** certificate with the same EKU, `CN=martelage rogue OCSP responder`: its answers are signed by a party no supplied anchor vouches for — the unanchored-responder arm |
| `ocsp-signerA-good.der` / `.pem` | the responder's answer for the sealer (serial `0A11`): `good`, window `2020-01-01 .. 2099-01-01`, in both encodings — `--ocsp-response` takes DER or PEM |
| `ocsp-signerA-revoked.der` | the same answer with the sealer's serial **revoked** `2021-06-01`, reason `keyCompromise` — the same entry the revoked CRL carries, one medium over |
| `ocsp-signerA-expired.der` | the same CA, same responder, same `good` — window `2020-01-01 .. 2021-01-01`, so it is expired on any host at any time, exactly as `crl-intermediateA-expired.pem` is |
| `ocsp-signerA-rogue.der` | the same `good`, signed by `ocsp-rogue`: a valid signature from a party that chains to nothing |
| `ocsp-signerC-good.der` | a well-formed `good` for serial `0A14` (`signerC`), a certificate **not in the vectors' chain**: a `good` is never carried across to another certificate |
| `crl-intermediateA-clean.pem` / `.der` | intermediate A's CRL with **no** entries, one in each encoding: the "checked clean" arm, and the arm that says `--revocation` takes PEM or DER |
| `crl-intermediateA-revoked.pem` | the same CRL with **one** entry: `signerA` (serial `0x0A11`) revoked `2021-06-01`, reason `keyCompromise` — the arm where the supplied material refuses the seal |
| `crl-intermediateA-expired.pem` | the same CA, same key, **no** entries, window `2020-01-01 .. 2021-01-01`: the CRL whose `nextUpdate` is in the past, on any host at any time |
| `crl-rootA-clean.pem` | root A's CRL, no entries: the CA that issued intermediate A, so the intermediate is spoken for |
| `crl-rootB-clean.pem` | root B's CRL, no entries: a perfectly valid CRL from a CA that issued **nothing** in the vectors' chain — the "wrong issuer" arm |
| `anchors/` | the verifier's trust store: root A. `--trust-anchors vectors/pki/anchors` |
| `anchors-b/` | root A **and** root B: the same store plus the one file that decides vector 36 |

## Dates are fixed, keys are not

Every certificate's validity window is set with `openssl x509 -not_before/-not_after`, so the dates do
not depend on the clock: `expired.crt.pem`, `intermediateA-expired.crt.pem` and `tsa-expired.crt.pem`
expired on 2021-01-01 and will be expired on any host at any time, and every other certificate is
valid until 2099-01-01. That is what makes vectors 40, 44 and 45 deterministic rather than vectors
with a documented time dependency.

The **key material is freshly generated** on each run of `tools/mkpki.sh`, so the certificate bytes —
and therefore the containers sealed with them — differ between rebuilds. The *verdicts* the vectors
assert do not, because the layout, the subjects and the dates are fixed. If you regenerate the PKI,
regenerate the containers too, or the shipped containers will be sealed by keys the tree no longer
holds:

```sh
sh tools/mkpki.sh     # rebuild vectors/pki (new keys, same dates and layout), then the CRLs and responses
sh tools/mkcrl.sh     # just the CRLs, from the certificates already here
sh tools/mkocsp.sh    # just the OCSP responses, from those certificates and the two responders
sh tools/mkp3.sh      # rebuild vectors/34..58 (packages, containers and the material directories)
```

All of them run offline, open no port, and need only `openssl` and `python3`. The OCSP responses are
produced by an `openssl ocsp -index` responder reading a **request file** (`-reqin`, never a port),
and are then **re-dated and re-signed** by the same responder key: `openssl ocsp` stamps a response
with the build second and refuses a non-positive `-ndays`/`-nmin` (MEASURED on 3.5.3), so the fixed
2020/2099/2021 windows these files carry can only be had by moving the two GeneralizedTime fields and
re-signing. `tools/mkocsp.sh`'s header states exactly what it rewrites. `tools/mkasic.py` is the container
builder; its docstring states the exact container shape it produces. `mkpki.sh` replaces the generated
material only — this README survives a rebuild, because a rebuild that deleted the tree's own account
of what the keys are would be a rebuild that lost information.

## What this PKI is not

It is not a model of eIDAS. There is no qualified trust service provider here, no qualified
certificate, no certificate policy worth the name, and no supervision of any kind. It is a set of
throwaway keys arranged so that each check `validator/p3-verify` performs has one arm in which it
passes and one arm in which it fails, and so that each of those arms differs from its control by
exactly one thing. Nothing in this repository is certified by anyone, and no claim of compliance with
eIDAS or with ETSI EN 319 162-1 is made or implied.
