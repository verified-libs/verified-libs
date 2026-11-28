#!/usr/bin/env python3
"""Build the public tree from the private repository (DECISIONS 2026-11-12).

Usage: public-export.py OUT_DIR          (OUT_DIR must not exist)
       public-export.py --check          (only report what blocks an export)

Takes the files committed at HEAD (no history, nothing uncommitted),
leaves out the paths in site/embargo-paths.txt, applies the embargo markup
in markdown files (site/embargo_strip.py), and then
refuses if any word from site/embargo.txt (case-insensitive) is still in a
file or a file name. It also refuses if a name from site/session-names.txt
(the names of the AI sessions that work on the project; a whole word,
case-insensitive) is in a file or a file name that would be exported: public
texts name no session (owner, 2026-11-26). Both lists are left out by path.
Nothing is pushed or published: the owner does that.

The records under records/ name the commit they were made at. They are
committed after that commit, so it is never the exported one. The export
therefore writes two files: EXPORTED_FROM (the exported commit) and
SAME_SOURCES (the records' commits whose test sources, TEST_SOURCES below,
are those of the exported commit; documentation aside). verify-build.sh
and repeat.sh rebuild a record from the exported tree if its commit is in
one of the two.

A record of a commit with other test sources may be shown if the tree
still builds, byte for byte, the image it was measured from, and runs and
judges it the same way (DECISIONS 2026-11-22). The export takes that from
two things: the host side of the test sources (side() below) is the same at
the record's commit and at HEAD, and records/rebuilt.json
(lab/tools/image-ledger.py: a rebuild of the record from this tree's
sources) says the image matches. Any other record cannot be checked
against the tree, and the export is refused. A stress record of which only
some libraries' images match is refused too, until the page data says per
library which record it rests on.

The records of benchmark version 2 (records/bench-v2, one per board and
configuration, eight images each) are held the same way, per record: the
ledger entry must be of the record as it is (one checksum over its eight
images, their addresses, the fixed part and the boot stub) and say that
the tree builds all of it. So a change of one library stops the export
for that library's records only, until they are measured again. On the
host side the files the images are built by (V2_BUILT_BY: the build
scripts, the list of configurations, the slot table) may differ, as the
rebuild shows what they build; any other host-side file (the decoder of
the result words, the runner, the board table) must be the record's, but
for recorded host fixes.

A host fix (records/host-fixes.json, DECISIONS 2026-11-23) is a recorded
change of one of the files in HOST_FIXABLE: the runner of benchmark version
2 and the two tools that make and check its records. They build no image.
Records of a commit whose image side is that of HEAD, and whose host side
differs from HEAD's only by recorded fixes of those files, pass as records
of the same sources. A fix that touches how the numbers are read from the
board or worked out is not a host fix: the series is measured again.

An archived series (records/archived.json, DECISIONS 2026-11-23) is a
published set of records that is no longer held against the tree at hand:
it is checked against its own commit, which stays in the public
repository's history. The export takes such records if they are byte for
byte the ones that were archived and the test sources of their commit are
those of the commit the series was published from.
`public-export.py --archive-digest COMMIT [PREFIX...]` prints the count and
checksum for a new entry of that file. An entry may have "paths", prefixes of
record paths under records/ (e.g. "bench-v2/nrf5340/"): it then archives only
those records of its commit, and the commit's other records are held as if
it had no entry (method version 3, DECISIONS 2026-11-26: the boards measured
again are archived, the others stay current). An entry none of whose
records is in the tree any more is a series kept only in the public history
it names (its public commit): nothing to check in the tree. Its records were
replaced at their paths by those measured again. A set that is only partly
gone, or changed, still stops the export.

The records of the CRC kind (records/crc, one per board and configuration,
kinds/crc/bench/crcrecords.py) have test sources of their own,
CRC_TEST_SOURCES: the kind's directory but for its host tests and proofs
(CRC_NOT_SOURCES), the board support under firmware/common, the programs of
benchmark version 2 the kind uses by import, and the three lab files. A
change elsewhere under firmware/ does not touch them, and a change in
kinds/crc does not touch the ring-buffer records; a change under
firmware/common counts for both. The export writes the CRC records'
commits whose test sources are those of HEAD (or those but for recorded
host fixes) to SAME_SOURCES_CRC, as SAME_SOURCES for the ring buffers
(kinds/crc/bench/crcverify.sh reads it).

A CRC record of a commit with other CRC test sources is held as a record
of benchmark version 2 is (DECISIONS 2026-11-24, the same-image rule for
the CRC kind): the ledger (records/rebuilt.json, entry crc/<board>/<file>)
must be of the record as it is (one checksum over its eight images, their
addresses, the fixed part, the boot stub, the toolchain image and the
layout) and say that kinds/crc/bench/crcverify.sh with VL_TREE=1 builds all
of it from the tree; and the host side must stand (crc_host_stands). The
CRC test sources are on three sides (crc_side()):
  image     compiled or linked into an image: the adapters, the reference,
            the bench program, the shims, the Rust crate, the pins of the
            libraries (libs.lock, generated.lock), the kind's Makefile,
            firmware/common's sources and linker scripts. A change is held
            by the rebuild.
  built by  host files that only build images (CRC_BUILT_BY): build.sh,
            onebuild.sh, onecrc.py, crcslots.py, configs.txt, slots.txt,
            boards.txt and ramtables.txt (which boards a configuration is
            built for, and which tables onecrc.py moves to RAM),
            crcany.models, fetch.sh, .gitignore of the kind;
            firmware/common's bundle.py and libc-objs.sh; version 2's
            onebundle.py and oneslots.py; lab/tools/source-commit.sh. A
            change is held by the rebuild, as an image file.
  host      what runs the images, reads the result words and writes and
            checks the records: run-crc.py, crcrecords.py, version 2's
            run-one.py and decode.py, firmware/common's uart_host.py and
            samd20/bin/probe-rs, lab/boards.conf, lab/tools/boardpower.sh,
            and crcverify.sh, the check of a record. Every file of the
            kind not named here is host side too. A change must lead to
            HEAD's file by recorded host fixes, which are allowed only for
            CRC_HOST_FIXABLE (the runner, the record writer and the check
            of a record) and run-one.py, already in HOST_FIXABLE; any
            other change stops every CRC record of that commit until the
            series is measured again. A recorded fix of run-one.py counts
            for the records of both kinds, so its entry (what it changes
            in the numbers, and its control) must cover both.
repeat.sh and crccompare.py measure nothing and check no record; they are
in CRC_NOT_SOURCES with the host tests and proofs.

The pools kind (records/pools, kinds/pools/bench/poolrecords.py) is held
by the same rule with lists of its own (KINDS): POOLS_TEST_SOURCES (its
directory, the board support, version 2's programs it imports, the three
lab files), POOLS_NOT_SOURCES (host tests, the proof, the check of
MemoryPool v0.1.0, the cross-size builds, and the host-only files they use:
ports/host, shims/host, extract.py and the kind's Makefile, which builds
host tests only; and claims.tsv, what the libraries document about
interrupts, which the pages show and no image or run uses; repeat.sh and
poolscompare.py, which measure nothing and check no record),
POOLS_BUILT_BY (onebuild.sh, onepool.py, poolslots.py,
configs.txt, slots.txt, boards.txt, fetch.sh, .gitignore, and the shared
files the CRC kind's list names) and POOLS_HOST_FIXABLE (run-pools.py,
poolrecords.py, poolverify.sh). Its records' commits go to
SAME_SOURCES_POOLS. A change in kinds/pools touches neither the ring
buffers' nor the CRC kind's records, and the reverse. Its ledger entries
(pools/<board>/<file>, held by "sources_pools") are not made yet by
image-ledger.py: until they are, a pools record of a commit with other
test sources than HEAD's (but for recorded host fixes) stops the export.

The pools concurrency series (records/pools-isr, kinds/pools-isr,
lab/plans/2026-11-27-pools-concurrency.md) is held by the same rule with
lists of its own: POOLS_ISR_TEST_SOURCES (its directory and every test
source of the pools kind, whose adapters, libraries and build its images
are made of), POOLS_ISR_NOT_SOURCES (its host check and the files only that
uses, its no-board tests, its job and smoke scripts, and the pools kind's
own POOLS_NOT_SOURCES),
POOLS_ISR_BUILT_BY (build.py, onebuild.sh, .gitignore, and the pools kind's
POOLS_BUILT_BY) and POOLS_ISR_HOST_FIXABLE (run-isr.py, isrrecords.py,
decode.py, covmap.py, bench/isrverify.sh). Its records' commits go to
SAME_SOURCES_POOLS_ISR. Its check of a record (bench/isrverify.sh) came
after the series: a recorded host fix from "none" (ABSENT) adds a host file
the record's commit did not have.
Its records carry one image each, not an image list: they are held by
isr_images_digest (the image's address and bytes, the boot stub, the bundle
and the toolchain image), not by crc_images_digest. A kind is held by the
ledger only if it has a check of a record (its "verify" in KINDS, the script
image-ledger.py rebuilds its records with); a kind without one fails
closed: a record of a commit whose sources differ from HEAD's stops the
export ("no check of a record ..."), whatever the ledger holds for it.
Nothing of the other kinds changes.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "site"))
from embargo_strip import strip_embargo   # noqa: E402


# What a record's firmware is built from and run with: firmware/ and the
# lab files its scripts use.
TEST_SOURCES = ["firmware", "lab/boards.conf", "lab/tools/source-commit.sh", "lab/tools/boardpower.sh"]
# The CRC kind (records/crc): what its images are built from and run with.
CRC_RECORDS = "records/crc/"
CRC_TEST_SOURCES = ["kinds/crc", "firmware/common"] + ["firmware/nrf5340-rb-bench/" + n for n in (
    "onebundle.py", "oneslots.py", "run-one.py", "decode.py")] + TEST_SOURCES[1:]
# In kinds/crc but neither built into an image nor used to build, run or record one: host tests, proofs,
# the comparisons of step 4, and the tools that repeat or compare runs without making or checking a record
# (repeat.sh, crccompare.py). Every other file of the directory counts, a new one too.
CRC_NOT_SOURCES = tuple("kinds/crc/" + n for n in (
    "proof/", "test_crc.c", "adapters_broken.c", "ref_check.c", "ref_check.py", "cross_main.c", "cross.sh",
    "loops.py", "sizes.py", "run.sh", "bench/test_crcrecords.py", "repeat.sh", "bench/crccompare.py"))
# Host files of the CRC kind that only build images: a change is held by the rebuild (image-ledger.py).
CRC_BUILT_BY = tuple("kinds/crc/" + n for n in (
    ".gitignore", "bench/build.sh", "bench/onebuild.sh", "bench/onecrc.py", "bench/crcslots.py", "configs.txt",
    "slots.txt", "crcany.models", "fetch.sh", "boards.txt", "ramtables.txt")) + ("firmware/common/bundle.py", "firmware/common/libc-objs.sh") + tuple(
    "firmware/nrf5340-rb-bench/" + n for n in ("onebundle.py", "oneslots.py")) + ("lab/tools/source-commit.sh",)
# Host files of the CRC kind a recorded fix may change without a new series: the runner, the record writer
# and the check of a record.
CRC_HOST_FIXABLE = ("kinds/crc/bench/run-crc.py", "kinds/crc/bench/crcrecords.py", "kinds/crc/bench/crcverify.sh")
# The pools kind (records/pools), held as the CRC kind: its own directory, the board support, the programs of
# version 2 it uses by import, and the three lab files.
POOLS_RECORDS = "records/pools/"
POOLS_TEST_SOURCES = ["kinds/pools", "firmware/common"] + ["firmware/nrf5340-rb-bench/" + n for n in (
    "onebundle.py", "oneslots.py", "run-one.py", "decode.py")] + TEST_SOURCES[1:]
# In kinds/pools but neither built into an image nor used to build, run or record one: the host tests and
# their files (the host ports and shims, CMSIS-RTX's extract, the kind's Makefile, which builds host tests
# only), the proof, the check of MemoryPool v0.1.0, the cross-size builds.
POOLS_NOT_SOURCES = tuple("kinds/pools/" + n for n in (
    "proof/", "checks/", "test_pool.c", "ports/host/", "shims/host/", "extract.py", "Makefile", "run.sh",
    "cross_main.c", "cross.sh", "sizes.py", "bench/test_poolrecords.py",
    "claims.tsv",    # what the libraries document about interrupts: shown on the pages, not used by an image or a run
    "repeat.sh", "bench/poolscompare.py"))   # repeat and compare runs without making or checking a record
POOLS_BUILT_BY = tuple("kinds/pools/" + n for n in (
    ".gitignore", "bench/onebuild.sh", "bench/onepool.py", "bench/poolslots.py", "configs.txt", "slots.txt",
    "boards.txt", "fetch.sh")) + ("firmware/common/bundle.py", "firmware/common/libc-objs.sh") + tuple(
    "firmware/nrf5340-rb-bench/" + n for n in ("onebundle.py", "oneslots.py")) + ("lab/tools/source-commit.sh",)
POOLS_HOST_FIXABLE = ("kinds/pools/bench/run-pools.py", "kinds/pools/bench/poolrecords.py", "kinds/pools/bench/poolverify.sh")
# The pools concurrency series (records/pools-isr): its images are built from the pools kind's sources and its
# own directory, so both count; its host check and tests do not.
POOLS_ISR_RECORDS = "records/pools-isr/"
POOLS_ISR_TEST_SOURCES = ["kinds/pools-isr"] + POOLS_TEST_SOURCES
POOLS_ISR_NOT_SOURCES = tuple("kinds/pools-isr/" + n for n in (
    "contract.c", "excl_host.h", "rtx_excl_prelude.h", "ARMCM_isr.h", "no_gthreads.h", "Makefile", "run.sh",
    "test_decode.py", "test_runner.py", "enqueue.sh", "smoke-check.sh")) + POOLS_NOT_SOURCES
POOLS_ISR_BUILT_BY = tuple("kinds/pools-isr/" + n for n in ("build.py", "onebuild.sh", ".gitignore")) + POOLS_BUILT_BY
POOLS_ISR_HOST_FIXABLE = tuple("kinds/pools-isr/" + n for n in (
    "run-isr.py", "isrrecords.py", "decode.py", "covmap.py", "bench/isrverify.sh"))
# The kinds with test sources of their own: kind -> what holds its records (the ring buffers are the rest
# of records/). "name" is the kind as the output says it, "same" the file of the export that lists the
# records' commits with HEAD's test sources (the kind's verify script reads it).
# "digest" is the checksum over what a record was measured from (a function of the record, set below, after the
# functions), "verify" the kind's check of a record, which image-ledger.py rebuilds its records with (None: the
# kind has none, and the ledger holds none of its records: they fail closed).
KINDS = {
    "crc": {"records": CRC_RECORDS, "sources": CRC_TEST_SOURCES, "not": CRC_NOT_SOURCES, "built_by": CRC_BUILT_BY,
            "name": "CRC", "same": "SAME_SOURCES_CRC", "verify": "kinds/crc/bench/crcverify.sh"},
    "pools": {"records": POOLS_RECORDS, "sources": POOLS_TEST_SOURCES, "not": POOLS_NOT_SOURCES,
              "built_by": POOLS_BUILT_BY, "name": "pools", "same": "SAME_SOURCES_POOLS",
              "verify": "kinds/pools/bench/poolverify.sh"},
    "pools-isr": {"records": POOLS_ISR_RECORDS, "sources": POOLS_ISR_TEST_SOURCES, "not": POOLS_ISR_NOT_SOURCES,
                  "built_by": POOLS_ISR_BUILT_BY, "name": "pools concurrency", "same": "SAME_SOURCES_POOLS_ISR",
                  "verify": "kinds/pools-isr/bench/isrverify.sh"},
}
RECORD_COMMIT = re.compile(r'"(?:source_commit|bench_commit)":\s*"([0-9a-f]{12,40})"|"commits":\s*\[([^\]]*)\]')


def git_id(rev_path):
    r = subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "-q", rev_path], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


# Compiled or linked into an image: a change shows in the image's checksum.
IMAGE_SUFFIXES = (".c", ".h", ".cpp", ".hpp", ".ld", ".mk", ".rs", ".toml", ".lock", ".S", ".s")
LEDGER = "records/rebuilt.json"
ARCHIVED = "records/archived.json"
HOST_FIXES = "records/host-fixes.json"
# The host-side files a recorded fix may change without a new series: they
# run images and write, collect and check records, and build nothing.
HOST_FIXABLE = ("firmware/nrf5340-rb-bench/run-one.py", "firmware/nrf5340-rb-bench/onerecords.py",
                "firmware/nrf5340-rb-bench/oneverify.sh") + CRC_HOST_FIXABLE + POOLS_HOST_FIXABLE + POOLS_ISR_HOST_FIXABLE
# Benchmark version 2 (records/bench-v2): the host-side files its images are
# built by. A change in one of them is held like a change in a source file:
# the record stands if the tree still builds its images, byte for byte, at
# the same addresses (DECISIONS 2026-11-23; the ledger, image-ledger.py).
V2_RECORDS = "records/bench-v2/"
V2_BUILT_BY = tuple("firmware/nrf5340-rb-bench/" + n for n in (
    "onebuild.sh", "onebundle.py", "oneslots.py", "configs.txt", "slots.txt", "fetch-libs.sh", "nrf5-sdk.sh"))


def v2_images_digest(rec):
    """One checksum for what a version 2 record was measured from: the
    fixed part, the boot stub, and each image's placement, address and
    bytes in flash."""
    lines = [rec["fixed_sha256"], rec["boot_image_sha256"]] + [
        f"{im['place']} {int(im['image_base'], 16):#x} {im['image_sha256']}" for im in sorted(rec["images"], key=lambda im: im["place"])]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def crc_images_digest(rec):
    """One checksum for what a CRC record was measured from: as
    v2_images_digest, and the toolchain image and the layout, which
    crcverify.sh compares too."""
    extra = [f"toolchain_image {rec.get('toolchain_image')}", f"layout {rec.get('layout')}"]
    return hashlib.sha256("\n".join([v2_images_digest(rec)] + extra).encode()).hexdigest()


def isr_images_digest(rec):
    """One checksum for what a pools concurrency record (pools-isr/1) was
    measured from: one image per record, so its address and flash bytes,
    the boot stub, the whole bundle the image was in, and the toolchain
    image. KeyError if a field is missing."""
    lines = [f"image_base {int(rec['image_base'], 16):#x}", f"image_sha256 {rec['image_sha256']}",
             f"boot_image_sha256 {rec['boot_image_sha256']}", f"bundle {rec['bundle']} {rec['bundle_sha256']}",
             f"toolchain_image {rec['toolchain_image']}"]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def side(path):
    """Which side of the test a file under TEST_SOURCES is on: "image"
    (compiled or linked into an image), None (documentation), or "host"
    (what the images are built, run and judged with: scripts, judges, the
    board table, and every file of a kind not known here)."""
    if path.endswith(".md"):
        return None
    if path.endswith(IMAGE_SUFFIXES) or os.path.basename(path) == "Makefile":
        return "image"
    return "host"


KINDS["crc"]["digest"] = KINDS["pools"]["digest"] = crc_images_digest
KINDS["pools-isr"]["digest"] = isr_images_digest


def kind_digest(rec, kind):
    """The kind's checksum of a record (KINDS "digest"), or None if the record lacks a field it needs."""
    try:
        return KINDS[kind]["digest"](rec)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


_ids = {}


def source_ids(commit, kind=None):
    """(all, host): a checksum over the test sources at commit, and over
    their host side alone; of the ring buffers, or with a kind of KINDS
    of that kind. (None, None) if the commit is not in the repository."""
    paths, skip = (KINDS[kind]["sources"], KINDS[kind]["not"]) if kind else (TEST_SOURCES, ())
    if (commit, kind) not in _ids:
        r = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "-z", commit, "--", *paths],
                           capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout:
            _ids[(commit, kind)] = (None, None)
        else:
            entries = sorted(e for e in r.stdout.split("\0") if e and side(e.split("\t", 1)[1])
                             and not e.split("\t", 1)[1].startswith(skip))
            host = [e for e in entries if side(e.split("\t", 1)[1]) == "host"]
            _ids[(commit, kind)] = tuple(hashlib.sha256("\n".join(x).encode()).hexdigest() for x in (entries, host))
    return _ids[(commit, kind)]


def same_sources(commit):
    """True if the test sources are the same at commit and at HEAD."""
    a = source_ids(commit)[0]
    return a is not None and a == source_ids("HEAD")[0]


def same_host_side(commit):
    a = source_ids(commit)[1]
    return a is not None and a == source_ids("HEAD")[1]


def kind_side(path, kind):
    """The side of a test source of a kind: "image", "built by" (its
    built_by list), None (documentation) or "host"."""
    if path in KINDS[kind]["built_by"]:
        return "built by"
    return side(path)


def crc_side(path):
    return kind_side(path, "crc")


def blobs(commit, kind=None):
    """path -> (side, blob) of the test sources at commit (with a kind of
    KINDS: of that kind, sides by kind_side()); {} if unknown."""
    if kind:
        paths, skip, sd = KINDS[kind]["sources"], KINDS[kind]["not"], (lambda p: kind_side(p, kind))
    else:
        paths, skip, sd = TEST_SOURCES, (), side
    r = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "-z", commit, "--", *paths],
                       capture_output=True, text=True)
    out = {}
    for e in (r.stdout.split("\0") if r.returncode == 0 else []):
        if not e:
            continue
        path = e.split("\t", 1)[1]
        if sd(path) and not path.startswith(skip):
            out[path] = (sd(path), e.split("\t", 1)[0].split()[2])
    return out


def host_fixes():
    """file -> {blob before: blob after} from records/host-fixes.json at
    HEAD. An entry that is not whole, or names a file outside HOST_FIXABLE,
    stops the export."""
    r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{HOST_FIXES}"], capture_output=True, text=True)
    steps = {}
    for e in (json.loads(r.stdout).get("fixes", []) if r.returncode == 0 else []):
        if e.get("file") not in HOST_FIXABLE or not all(str(e.get(k, "")).strip() for k in ("from", "to", "what", "numbers", "control")):
            sys.exit(f"{HOST_FIXES}: an entry for {e.get('file')} is not whole or not of a file in HOST_FIXABLE")
        steps.setdefault(e["file"], {})[e["from"]] = e["to"]
    return steps


def host_fixed(commit):
    """True if the test sources at commit are those of HEAD but for
    recorded host fixes: same image side, the same files, and every
    differing host file leads to HEAD's by the steps of host-fixes.json."""
    a, b = blobs(commit), blobs("HEAD")
    if not a or set(a) != set(b):
        return False
    steps = host_fixes()
    for path in a:
        if a[path] == b[path]:
            continue
        at, seen = a[path][1], set()
        while at != b[path][1] and at in steps.get(path, {}) and at not in seen:
            seen.add(at)
            at = steps[path][at]
        if a[path][0] != "host" or at != b[path][1]:
            return False
    return True


def v2_host_stands(commit):
    """True if a version 2 record of commit can stand on a rebuild of its
    images: every host-side file that differs from HEAD's is one the images
    are built by (V2_BUILT_BY), or leads to HEAD's by recorded fixes."""
    a, b = blobs(commit), blobs("HEAD")
    if not a:
        return False
    steps = host_fixes()
    for path in set(a) | set(b):
        if a.get(path) == b.get(path) or (a.get(path) or b[path])[0] == "image" or path in V2_BUILT_BY:
            continue
        if path not in a or path not in b:
            return False
        at, seen = a[path][1], set()
        while at != b[path][1] and at in steps.get(path, {}) and at not in seen:
            seen.add(at)
            at = steps[path][at]
        if at != b[path][1]:
            return False
    return True


# The "from" of a recorded host fix that adds a host file the record's commit did not have (a kind's check of a
# record written after its series). Only the kinds' rule (crc_host_fixed, crc_host_stands) reads it.
ABSENT = "none"


def crc_fix_leads(a, b, path):
    """True if the blob of path at a (ABSENT if a has no such file) leads to its blob at b by recorded host fixes."""
    steps = host_fixes()
    at, seen = (a[path][1] if path in a else ABSENT), set()
    while at != b[path][1] and at in steps.get(path, {}) and at not in seen:
        seen.add(at)
        at = steps[path][at]
    return at == b[path][1]


def crc_host_fixed(commit, kind="crc"):
    """True if the test sources of a kind (default the CRC kind) at commit
    are those of HEAD but for recorded fixes of host files: the same files,
    and every one that differs is host side and leads to HEAD's by the steps
    of host-fixes.json."""
    a, b = blobs(commit, kind), blobs("HEAD", kind)
    if not a or set(a) - set(b):
        return False
    return all(a.get(p) == b[p] or (b[p][0] == "host" and (p not in a or a[p][0] == "host") and crc_fix_leads(a, b, p))
               for p in b)


def crc_host_stands(commit, kind="crc"):
    """True if a record of a kind (default the CRC kind) of commit can stand
    on a rebuild of its images: every host-side file is HEAD's or leads to
    it by recorded fixes; image files and the files that only build images
    (the kind's built_by) may differ, as the rebuild shows what they build."""
    a, b = blobs(commit, kind), blobs("HEAD", kind)
    if not a:
        return False
    for path in set(a) | set(b):
        if a.get(path) == b.get(path) or (a.get(path) or b[path])[0] in ("image", "built by"):
            continue
        if path not in b or (path in a and a[path][0] != "host") or b[path][0] != "host" or not crc_fix_leads(a, b, path):
            return False
    return True


def ledger(kind=None):
    """Record name -> entry of records/rebuilt.json at HEAD, if the ledger
    was made from the test sources of HEAD; else {}. The ring buffers'
    entries are held by the checksum of their sources ("sources"), a kind's
    of KINDS (named <kind>/...) by that of the kind's ("sources_<kind>")."""
    r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{LEDGER}"], capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    led = json.loads(r.stdout)
    if kind:
        if led.get("sources_" + kind) != source_ids("HEAD", kind)[0]:
            return {}
        return {n: e for n, e in led.get("records", {}).items() if n.startswith(kind + "/")}
    if led.get("sources") != source_ids("HEAD")[0]:
        return {}
    return {n: e for n, e in led.get("records", {}).items() if not n.startswith(tuple(k + "/" for k in KINDS))}


def archived():
    """Record commit (12 digits) -> [entries of records/archived.json at HEAD]. An entry with "paths"
    (prefixes of record paths under records/, e.g. "crc/nrf5340/") archives only the records of its
    commit under them; the commit's other records are held as if it had no entry (method version 3:
    the records of the boards measured again are archived, those of the other boards stay current)."""
    r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{ARCHIVED}"], capture_output=True, text=True)
    out = {}
    for e in (json.loads(r.stdout)["series"] if r.returncode == 0 else []):
        out.setdefault(e["commit"][:12], []).append(e)
    return out


def under(name, entry):
    """True if a record (its path under records/) is one an archive entry covers."""
    return entry.get("paths") is None or name.startswith(tuple(entry["paths"]))


def records_digest(recs):
    """A checksum over a commit's records: their paths and contents."""
    return hashlib.sha256("".join(f"{sha}  {path}\n" for path, sha in sorted(recs)).encode()).hexdigest()


def not_checked(e):
    """why a record the ledger holds as "not checked" stops: its rebuild did not end in a comparison (a library
    fetch that failed is said as such, image-ledger.py FETCH_FAULT); it is not a record HEAD builds another image of"""
    note = " ".join(e.get("note", "").split())
    note = note if len(note) <= 160 else note[:157] + "..."
    if note.startswith("could not fetch the libraries"):
        return f"could not fetch the libraries, so not checked ({LEDGER}): {note[len('could not fetch the libraries: '):]}"
    return f"not checked ({LEDGER}): {note or 'no note'}"


def archive_fault(entry, recs, kind=None):
    """Why the records naming an archived commit cannot pass as that series, or None (a kind of KINDS:
    the test sources of that kind are compared)."""
    a, b = source_ids(entry["commit"], kind)[0], source_ids(entry["exported_from"], kind)[0]
    if a is None or a != b:
        return f"the test sources of its commit are not those of {entry['exported_from'][:12]}, which {ARCHIVED} says it was published from"
    if len(recs) != entry["records"] or records_digest(recs) != entry["records_sha256"]:
        return f"the records are not the ones archived ({len(recs)} now, {entry['records']} in {ARCHIVED}, or a changed file)"
    return None


def lines_of(path):
    with open(os.path.join(ROOT, path)) as fh:
        return [l.strip() for l in fh if l.strip() and not l.lstrip().startswith("#")]


def main():
    check_only = sys.argv[1:] == ["--check"]
    digest_of = sys.argv[2][:12] if len(sys.argv) >= 3 and sys.argv[1] == "--archive-digest" else None
    check_only = check_only or bool(digest_of)
    if not check_only and (len(sys.argv) != 2 or sys.argv[1].startswith("-")):
        sys.exit(__doc__)   # also for --help: an option is never taken as OUT_DIR
    out = None if check_only else os.path.abspath(sys.argv[1])
    if out and os.path.exists(out):
        sys.exit(f"{out} exists")
    if out:   # the export test's cache of rebuild results (image-ledger.py --test-cache) is never exported
        r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{LEDGER}"], capture_output=True, text=True)
        if r.returncode == 0 and "cache_used" in json.loads(r.stdout):
            sys.exit(f"{LEDGER} at HEAD was made with the export test's cache (cache_used): no export; make it again without it")
    words = [w.lower() for w in lines_of("site/embargo.txt")]
    skip = [p.rstrip("/") for p in lines_of("site/embargo-paths.txt")]
    # session names: whole words, case-insensitive (site/session-names.txt, one per line)
    session = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(w) for w in lines_of("site/session-names.txt"))
                         + r")(?![A-Za-z0-9_])", re.I)
    named = []   # (file, line or 0 for the file name, the word)
    files = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", "-z", "HEAD"], capture_output=True, check=True,
                           text=True).stdout.split("\0")
    bad, kept, left_out = [], 0, 0
    rec_commits = {}   # commit named by a record under records/ -> the records' (file name, fw_sha256)
    rec_files = {}     # the same commit -> the records' (path, checksum of the file)
    k_commits = {k: {} for k in KINDS}   # kind -> commit named by a record under its records -> (name, digest)
    k_files = {k: {} for k in KINDS}     # kind -> the same commit -> (file, its SHA-256), for an archived series
    for f in filter(None, files):
        if any(f == p or f.startswith(p + "/") for p in skip):
            left_out += 1
            continue
        data = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{f}"], capture_output=True,
                              check=True).stdout
        try:
            text = data.decode()
        except UnicodeDecodeError:
            text = None
        if text is not None and f.endswith(".md"):
            text = strip_embargo(text)
            data = text.encode()
        hay = (f + "\n" + (text or "")).lower()
        hits = sorted({w for w in words if w in hay})
        if hits:
            bad.append((f, hits))
            continue
        names = [(0, m.group(1)) for m in session.finditer(f)] + [
            (i, m.group(1)) for i, line in enumerate((text or "").splitlines(), 1) for m in session.finditer(line)]
        if names:
            named += [(f, i, w) for i, w in names]
            continue
        kept += 1
        kind = next((k for k, v in KINDS.items() if f.startswith(v["records"])), None)
        if text is not None and kind and f.endswith(".json"):
            rec = json.loads(text)
            c = rec.get("bench_commit") or "unknown"
            digest = kind_digest(rec, kind)
            k_commits[kind].setdefault(c[:12], []).append((f[len("records/"):], digest))
            k_files[kind].setdefault(c[:12], []).append((f, hashlib.sha256(data).hexdigest()))
        elif text is not None and f.startswith("records/") and f.endswith(".json"):
            found = set()
            for one, many in RECORD_COMMIT.findall(text):
                found.update([one[:12]] if one else re.findall(r"[0-9a-f]{12,40}", many))
            sha = re.search(r'"fw_sha256":\s*"([0-9a-f]{64})"', text)
            name, sha = os.path.basename(f), sha.group(1) if sha else None
            if f.startswith(V2_RECORDS):   # one record per board and configuration: named by its path, held by its images
                name, sha = f[len("records/"):], v2_images_digest(json.loads(text))
            for c in found:
                rec_commits.setdefault(c[:12], []).append((name, sha))
                rec_files.setdefault(c[:12], []).append((f, hashlib.sha256(data).hexdigest()))
        if out:
            dst = os.path.join(out, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(data)
            mode = os.stat(os.path.join(ROOT, f)).st_mode if os.path.exists(os.path.join(ROOT, f)) else 0o644
            os.chmod(dst, mode & 0o777)
    same = sorted(c for c in rec_commits if same_sources(c))
    fixed = sorted(c for c in set(rec_commits) - set(same) if host_fixed(c))
    n_fixed = sum(len(rec_commits[c]) for c in fixed)
    same = sorted(same + fixed)
    led = ledger()
    if digest_of:
        pre = tuple(sys.argv[3:])
        recs = [x for x in rec_files.get(digest_of, []) + sum((v.get(digest_of, []) for v in k_files.values()), [])
                if not pre or x[0][len("records/"):].startswith(pre)]
        print(json.dumps({"commit": digest_of, "records": len(recs), "records_sha256": records_digest(recs)}, indent=1))
        return
    arch, n_arch = archived(), {}
    rebuilt, other = 0, {}   # other: commit -> [(record, why not)]
    for c in sorted(set(rec_commits) - set(same)):
        rest = rec_commits[c]
        for entry in arch.get(c, []):
            mine = [(n, s) for n, s in rest if under(n, entry)]
            files = [(f, h) for f, h in rec_files[c] if under(f[len("records/"):], entry)]
            # an entry none of whose records is in the tree any more: the series lives in the public history
            # its entry names (method version 3: the measured-again boards' records replaced at their paths)
            why = archive_fault(entry, files) if files else None
            if why is None:
                n_arch.update({entry["name"]: n_arch.get(entry["name"], 0) + len(files)} if files else {})
            else:
                other.setdefault(c, []).extend((name, why) for name, _ in mine)
            rest = [(n, s) for n, s in rest if not under(n, entry)]
        for name, sha in rest:
            e = led.get(name)
            v2 = name.startswith(V2_RECORDS[len("records/"):])
            if not (v2_host_stands(c) if v2 else same_host_side(c)):
                why = "the scripts and judges at that commit are not those of HEAD (or the commit is unknown)"
            elif sha is None:
                why = "it has no image checksum, so it is made again when the sources change"
            elif e is None:
                why = f"no rebuild from the sources of HEAD in {LEDGER} (lab/tools/image-ledger.py)"
            elif e.get("images_sha256" if v2 else "fw_sha256") != sha:
                why = f"{LEDGER} holds another checksum for it"
            elif e.get("result") == "not checked":
                why = not_checked(e)
            elif e.get("result") != "match":
                why = "HEAD builds another image" + (f" (libraries {', '.join(e['libs_differ'])})" if e.get("libs_differ") else "")
            else:
                rebuilt += 1
                continue
            other.setdefault(c, []).append((name, why))
    k_same, k_rebuilt, k_other = {}, {}, {}   # kind -> commits; records rebuilt; commit -> [(record, why not)]
    for kind, kv in KINDS.items():
        commits, kfiles = k_commits[kind], k_files[kind]
        same_k = sorted(c for c in commits if source_ids(c, kind)[0] is not None
                        and source_ids(c, kind)[0] == source_ids("HEAD", kind)[0])
        fixed_k = sorted(c for c in set(commits) - set(same_k) if crc_host_fixed(c, kind))
        k_same[kind] = same_k = sorted(same_k + fixed_k)
        led_k, k_rebuilt[kind], other_k = ledger(kind), 0, {}
        k_other[kind] = other_k
        for c in sorted(set(commits) - set(same_k)):
            rest = commits[c]
            for entry in arch.get(c, []):
                mine = [(n, d) for n, d in rest if under(n, entry)]
                files = [(f, h) for f, h in kfiles[c] if under(f[len("records/"):], entry)]
                why = archive_fault(entry, files, kind) if files else None
                if why is None:
                    n_arch.update({entry["name"]: n_arch.get(entry["name"], 0) + len(files)} if files else {})
                else:
                    other_k.setdefault(c, []).extend((name, why) for name, _ in mine)
                rest = [(n, d) for n, d in rest if not under(n, entry)]
            for name, digest in rest:
                e = led_k.get(name)
                if not crc_host_stands(c, kind):
                    why = f"the host side of the {kv['name']} kind at that commit is not that of HEAD (or the commit is unknown)"
                elif not kv.get("verify"):
                    why = (f"the {kv['name']} kind has no check of a record yet (no rebuild script), "
                           f"so no rebuild in {LEDGER} can hold it")
                elif digest is None:
                    why = "the record has no image checksums"
                elif e is None:
                    why = f"no rebuild from the sources of HEAD in {LEDGER} (lab/tools/image-ledger.py)"
                elif e.get("images_sha256") != digest:
                    why = f"{LEDGER} holds another checksum for it"
                elif e.get("result") == "not checked":
                    why = not_checked(e)
                elif e.get("result") != "match":
                    why = "HEAD builds another image"
                else:
                    k_rebuilt[kind] += 1
                    continue
                other_k.setdefault(c, []).append((name, why))
    n_other = sum(len(v) for v in other.values()) + sum(len(v) for o in k_other.values() for v in o.values())
    print(f"{kept} files clean, {left_out} left out by path, {len(bad)} with embargoed words, "
          f"{len({f for f, _, _ in named})} with session names, "
          f"{n_other} records that cannot be rebuilt from this tree"
          + (f" ({rebuilt} of other commits whose image this tree builds)" if rebuilt else "")
          + (f", {n_fixed} records made before a recorded host fix" if n_fixed else "")
          + "".join(f", {n} records of the archived series \"{name}\"" for name, n in sorted(n_arch.items()))
          + "".join((f", {sum(len(k_commits[k][c]) for c in k_same[k])} {v['name']} records" if k_commits[k] else "")
                    + (f" ({k_rebuilt[k]} more of other commits whose images this tree builds)" if k_rebuilt[k] else "")
                    for k, v in KINDS.items()))
    for f, hits in bad:
        print(f"  EMBARGO: {f}: {', '.join(hits)}")
    for f, i, w in named:
        print(f"  SESSION NAME: {f}:{i}: {w}" if i else f"  SESSION NAME: {f} (its name): {w}")
    for c, recs in other.items():
        print(f"  RECORDS: {len(recs)} under records/ name commit {c}, whose test sources "
              f"({', '.join(TEST_SOURCES)}) are not those of HEAD:")
        whys = {}
        for name, why in recs:
            whys.setdefault(why, []).append(name)
        for why, names in whys.items():
            print(f"    {len(names)}: {why}: {', '.join(names[:8])}{' ...' if len(names) > 8 else ''}")
    for kind, kv in KINDS.items():
        for c, recs in sorted(k_other[kind].items()):
            print(f"  RECORDS: {len(recs)} under {kv['records']} name commit {c}, whose test sources of the {kv['name']} kind "
                  f"are not those of HEAD (or the commit is unknown):")
            whys = {}
            for name, why in recs:
                whys.setdefault(why, []).append(name)
            for why, names in whys.items():
                print(f"    {len(names)}: {why}: {', '.join(names[:8])}{' ...' if len(names) > 8 else ''}")
    if bad or named or other or any(k_other.values()):
        if out:
            print(f"export refused; {out} is incomplete, delete it")
        sys.exit(1)
    if out:
        # The commit the tree is taken from: lab/tools/verify-build.sh rebuilds
        # the records of this commit from a tree without history.
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, check=True,
                              text=True).stdout.strip()
        with open(os.path.join(out, "EXPORTED_FROM"), "w") as fh:
            fh.write(head + "\n")
        # The records' own commits: same test sources as HEAD, or the same
        # but for recorded host fixes (checked above).
        with open(os.path.join(out, "SAME_SOURCES"), "w") as fh:
            fh.write("".join(c + "\n" for c in same))
        for kind, kv in KINDS.items():
            if k_commits[kind]:
                with open(os.path.join(out, kv["same"]), "w") as fh:
                    fh.write("".join(c + "\n" for c in k_same[kind]))


if __name__ == "__main__":
    main()
