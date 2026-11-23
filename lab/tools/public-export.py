#!/usr/bin/env python3
"""Build the public tree from the private repository (DECISIONS 2026-11-12).

Usage: public-export.py OUT_DIR          (OUT_DIR must not exist)
       public-export.py --check          (only report what blocks an export)

Takes the files committed at HEAD (no history, nothing uncommitted),
leaves out the paths in site/embargo-paths.txt, applies the embargo markup
in markdown files (site/embargo_strip.py), and then
refuses if any word from site/embargo.txt (case-insensitive) is still in a
file or a file name. Nothing is pushed or published: the owner does that.

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
`public-export.py --archive-digest COMMIT` prints the count and checksum
for a new entry of that file.
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
                "firmware/nrf5340-rb-bench/oneverify.sh")
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


_ids = {}


def source_ids(commit):
    """(all, host): a checksum over the test sources at commit, and over
    their host side alone. (None, None) if the commit is not in the
    repository."""
    if commit not in _ids:
        r = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "-z", commit, "--", *TEST_SOURCES],
                           capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout:
            _ids[commit] = (None, None)
        else:
            entries = sorted(e for e in r.stdout.split("\0") if e and side(e.split("\t", 1)[1]))
            host = [e for e in entries if side(e.split("\t", 1)[1]) == "host"]
            _ids[commit] = tuple(hashlib.sha256("\n".join(x).encode()).hexdigest() for x in (entries, host))
    return _ids[commit]


def same_sources(commit):
    """True if the test sources are the same at commit and at HEAD."""
    a = source_ids(commit)[0]
    return a is not None and a == source_ids("HEAD")[0]


def same_host_side(commit):
    a = source_ids(commit)[1]
    return a is not None and a == source_ids("HEAD")[1]


def blobs(commit):
    """path -> (side, blob) of the test sources at commit; {} if unknown."""
    r = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "-z", commit, "--", *TEST_SOURCES],
                       capture_output=True, text=True)
    out = {}
    for e in (r.stdout.split("\0") if r.returncode == 0 else []):
        if e and side(e.split("\t", 1)[1]):
            out[e.split("\t", 1)[1]] = (side(e.split("\t", 1)[1]), e.split("\t", 1)[0].split()[2])
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


def ledger():
    """Record file name -> entry of records/rebuilt.json at HEAD, if the
    ledger was made from the test sources of HEAD; else {}."""
    r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{LEDGER}"], capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    led = json.loads(r.stdout)
    return led.get("records", {}) if led.get("sources") == source_ids("HEAD")[0] else {}


def archived():
    """Record commit (12 digits) -> entry of records/archived.json at HEAD."""
    r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{ARCHIVED}"], capture_output=True, text=True)
    return {e["commit"][:12]: e for e in json.loads(r.stdout)["series"]} if r.returncode == 0 else {}


def records_digest(recs):
    """A checksum over a commit's records: their paths and contents."""
    return hashlib.sha256("".join(f"{sha}  {path}\n" for path, sha in sorted(recs)).encode()).hexdigest()


def archive_fault(entry, recs):
    """Why the records naming an archived commit cannot pass as that series, or None."""
    a, b = source_ids(entry["commit"])[0], source_ids(entry["exported_from"])[0]
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
    digest_of = sys.argv[2][:12] if len(sys.argv) == 3 and sys.argv[1] == "--archive-digest" else None
    check_only = check_only or bool(digest_of)
    if not check_only and (len(sys.argv) != 2 or sys.argv[1].startswith("-")):
        sys.exit(__doc__)   # also for --help: an option is never taken as OUT_DIR
    out = None if check_only else os.path.abspath(sys.argv[1])
    if out and os.path.exists(out):
        sys.exit(f"{out} exists")
    words = [w.lower() for w in lines_of("site/embargo.txt")]
    skip = [p.rstrip("/") for p in lines_of("site/embargo-paths.txt")]
    files = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", "-z", "HEAD"], capture_output=True, check=True,
                           text=True).stdout.split("\0")
    bad, kept, left_out = [], 0, 0
    rec_commits = {}   # commit named by a record under records/ -> the records' (file name, fw_sha256)
    rec_files = {}     # the same commit -> the records' (path, checksum of the file)
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
        kept += 1
        if text is not None and f.startswith("records/") and f.endswith(".json"):
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
        recs = rec_files.get(digest_of, [])
        print(json.dumps({"commit": digest_of, "records": len(recs), "records_sha256": records_digest(recs)}, indent=1))
        return
    arch, n_arch = archived(), {}
    rebuilt, other = 0, {}   # other: commit -> [(record, why not)]
    for c in sorted(set(rec_commits) - set(same)):
        if c in arch:
            why = archive_fault(arch[c], rec_files[c])
            if why is None:
                n_arch[arch[c]["name"]] = len(rec_files[c])
            else:
                other[c] = [(name, why) for name, _ in rec_commits[c]]
            continue
        for name, sha in rec_commits[c]:
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
            elif e.get("result") != "match":
                why = "HEAD builds another image" + (f" (libraries {', '.join(e['libs_differ'])})" if e.get("libs_differ") else "")
            else:
                rebuilt += 1
                continue
            other.setdefault(c, []).append((name, why))
    n_other = sum(len(v) for v in other.values())
    print(f"{kept} files clean, {left_out} left out by path, {len(bad)} with embargoed words, "
          f"{n_other} records that cannot be rebuilt from this tree"
          + (f" ({rebuilt} of other commits whose image this tree builds)" if rebuilt else "")
          + (f", {n_fixed} records made before a recorded host fix" if n_fixed else "")
          + "".join(f", {n} records of the archived series \"{name}\"" for name, n in sorted(n_arch.items())))
    for f, hits in bad:
        print(f"  EMBARGO: {f}: {', '.join(hits)}")
    for c, recs in other.items():
        print(f"  RECORDS: {len(recs)} under records/ name commit {c}, whose test sources "
              f"({', '.join(TEST_SOURCES)}) are not those of HEAD:")
        whys = {}
        for name, why in recs:
            whys.setdefault(why, []).append(name)
        for why, names in whys.items():
            print(f"    {len(names)}: {why}: {', '.join(names[:8])}{' ...' if len(names) > 8 else ''}")
    if bad or other:
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


if __name__ == "__main__":
    main()
