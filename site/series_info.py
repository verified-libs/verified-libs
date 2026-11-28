#!/usr/bin/env python3
"""Which method version a board's records are of, and which archived series
held the board's records before (records/archived.json), for the pages and
their data: one place, so that the results pages, the comparison pages'
data and the MCP answers say the same.

- The method version of a record is read from its schema: "rb-bench/3"
  (ring buffers) and "crc-bench/2" (CRC) are records of method version 3,
  with the board's option registers (method.html#log-2026-11-26-v3); "rb-bench/2"
  and "crc-bench/1" are of method version 2.
- An archived series covers a board's records where one of its "paths" is
  the board's records directory (e.g. "bench-v2/stm32h723/"). It is named
  for the board only where the board's present records are of other
  commits than the series' commit, that is where newer records replaced
  the archived ones in the same paths. It is linked at its public commit
  (the public repository keeps it there, with the tools to check it).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_TREE = "https://github.com/verified-libs/verified-libs/tree/"
METHOD_3 = {"rb-bench/3", "crc-bench/2", "pools-bench/1"}   # the pools kind is measured only under method version 3
SINCE = {2: "2026-11-23", 3: "2026-11-26"}   # method.html change log: one image per configuration; the clock rule


def method_version(schema):
    """3 for the record versions of method version 3, else 2 (the records of benchmark version 2 and the CRC kind)."""
    return 3 if schema in METHOD_3 else 2


def archived_for(records_prefix, commits, path=None):
    """The archived series that held the records under records/<records_prefix> (e.g. "bench-v2/stm32h723/") before
    the present ones, which are of `commits`: [{name, commit, public_commit, url}], in the file's order."""
    path = path or os.path.join(ROOT, "records/archived.json")
    if not os.path.exists(path):
        return []
    out = []
    for s in json.load(open(path))["series"]:
        if records_prefix not in s.get("paths", []):
            continue
        if any(c.startswith(s["commit"]) or s["commit"].startswith(c) for c in commits):
            continue   # the present records are the archived ones (not replaced yet)
        out.append({"name": s["name"], "commit": s["commit"], "public_commit": s["public_commit"],
                    "url": PUBLIC_TREE + s["public_commit"] + "/records/" + records_prefix.rstrip("/")})
    return out


def unchanged_under_3(records_prefix, path=None):
    """True where method version 3 changed nothing on the board: archived.json has series archived for method
    version 3 (entries with "paths"), and none of them covers this board's records directory."""
    path = path or os.path.join(ROOT, "records/archived.json")
    if not os.path.exists(path):
        return False
    ser = [s for s in json.load(open(path))["series"] if s.get("paths")]
    return bool(ser) and not any(records_prefix in s["paths"] for s in ser)


def method_text(version, clock_hz, archived, unchanged=False, link=False):
    """The sentence per board: the method version, the clock, and what came before. link: markdown, each archived
    series linked at its public commit."""
    mhz = f"{clock_hz / 1e6:.0f} MHz"
    if version == 3:
        t = f"Method version 3, at {mhz}, with the board's option registers in every record."
    elif unchanged:
        t = (f"Method version 2, at {mhz}. Method version 3 changed nothing on this board: its images are built "
             f"byte for byte the same, so these records stand.")
    else:
        t = f"Method version 2, at {mhz}."
    if archived:
        t += " Before method version 3 this board's records were " + "; ".join(
            (f"the archived series [\"{a['name']}\"]({a['url']}) (public commit `{a['public_commit'][:7]}`)" if link
             else f"the archived series \"{a['name']}\" (public commit {a['public_commit'][:7]})") for a in archived) + "."
    return t
