#!/usr/bin/env python3
"""Compose SKILL.md over the generated instruction fragments from ansvar-workflow-mcp.

This repository is the canonical home of the regulatory-threat-model skill, and
it is a CONSUMER of the shared workflow instruction library, never an author of
it. Two sections of SKILL.md — the run loop and the delivery contract — are
compiled upstream (`instructions/shared/*.md` into `instructions/dist/fragments/`),
released with a manifest carrying a sha256 per fragment, and pinned here by
commit plus manifest hash in scripts/fragments.pin.json.

Editing the text between the GENERATED markers by hand is a build break, not a
change: fix it upstream, re-release, re-pin, re-run this script.

Two lanes, deliberately:

  import (default)   Needs a local wf-mcp checkout. Reads the pinned bytes with
                     `git show <commit>:<path>` — git cat-file semantics, never
                     the working tree, so a dirty or stale checkout cannot leak
                     into a publication. Verifies them against both the pin and
                     the released manifest, vendors them into fragments/, and
                     rewrites the marked blocks in SKILL.md.

  --check            Fully local: no checkout, no network. Verifies the chain
                     pin -> vendored fragments -> marked blocks. This is what CI
                     runs, because CI has no wf-mcp checkout.

Usage:
  python3 scripts/compose.py [--source <wf-mcp checkout>]
  python3 scripts/compose.py --check

Re-pin recipe:
  1. git -C <wf-mcp> fetch origin
     git -C <wf-mcp> log --oneline origin/main -- instructions/
  2. Hash the released manifest at the commit you want:
     git -C <wf-mcp> show <commit>:instructions/dist/manifest.json | sha256sum
  3. In scripts/fragments.pin.json set "commit" and "manifest_sha256", and copy
     each fragment's sha256 from that manifest's "fragments" array into the
     matching block entry.
  4. python3 scripts/compose.py --source <wf-mcp>
  5. READ THE SKILL.md DIFF. A fragment can change in a way that contradicts a
     hand-written section: the hand sections defer to these blocks rather than
     restating them, and a re-pin that breaks that deference is an editorial fix
     here, not a revert upstream. Tier facts are hand-owned — the fragments
     carry none by design.
  6. python3 scripts/compose.py --check && git add -A && git commit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN_PATH = ROOT / "scripts" / "fragments.pin.json"
SKILL_PATH = ROOT / "SKILL.md"
UPSTREAM_MANIFEST = "instructions/dist/manifest.json"
DEFAULT_SOURCE = ROOT.parent / "ansvar-workflow-mcp"

BEGIN = "<!-- BEGIN GENERATED: {id} @ pin -->"
END = "<!-- END GENERATED: {id} -->"

FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})(\s+)(.*)$")


def fail(message: str) -> None:
    sys.stderr.write(f"compose: {message}\n")
    raise SystemExit(1)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pin() -> dict:
    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"no pin file at {PIN_PATH}")
    except json.JSONDecodeError as exc:
        fail(f"pin file is not valid JSON: {exc}")
    for key in ("repo", "commit", "manifest_sha256", "blocks"):
        if key not in pin:
            fail(f'pin file is missing "{key}"')
    if not pin["blocks"]:
        fail("pin file declares no blocks")
    for block in pin["blocks"]:
        for key in ("id", "path", "sha256", "vendored", "heading_shift"):
            if key not in block:
                fail(f'pin block {block.get("id", "<unnamed>")} is missing "{key}"')
    return pin


def shift_headings(text: str, levels: int) -> str:
    """Shift ATX heading levels by `levels`, leaving fenced code blocks alone.

    A pure, deterministic transform. It exists so a fragment authored at one
    heading depth can nest at another without anyone hand-editing the generated
    bytes. Both blocks currently compose at their native depth (heading_shift 0),
    which makes this the identity transform — the fragments' own H2 roots are
    exactly the section level they occupy in SKILL.md.
    """
    if levels == 0:
        return text
    out: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.split("\n"):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, ""
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        heading = HEADING_RE.match(line)
        if heading:
            depth = len(heading.group(1)) + levels
            if not 1 <= depth <= 6:
                fail(
                    f"heading_shift {levels:+d} pushes "
                    f'"{line.strip()}" to depth {depth}, outside H1-H6'
                )
            out.append("#" * depth + heading.group(2) + heading.group(3))
            continue
        out.append(line)
    return "\n".join(out)


def render(block: dict, raw: bytes) -> str:
    return shift_headings(raw.decode("utf-8"), block["heading_shift"]).strip("\n")


def git_show(source: Path, commit: str, path: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(source), "show", f"{commit}:{path}"],
            check=True,
            capture_output=True,
        ).stdout
    except FileNotFoundError:
        fail("git is not on PATH")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        fail(f"cannot read {path} at {commit[:12]} in {source}: {detail}")


def block_bounds(text: str, block_id: str) -> tuple[int, int]:
    begin, end = BEGIN.format(id=block_id), END.format(id=block_id)
    if text.count(begin) != 1 or text.count(end) != 1:
        fail(
            f"SKILL.md must carry exactly one {begin} and one {end} "
            f"(found {text.count(begin)} and {text.count(end)})"
        )
    start, stop = text.index(begin), text.index(end)
    if stop < start:
        fail(f"{block_id}: END marker precedes BEGIN marker")
    return start + len(begin), stop


def read_block(text: str, block_id: str) -> str:
    start, stop = block_bounds(text, block_id)
    return text[start:stop].strip("\n")


def write_block(text: str, block_id: str, body: str) -> str:
    start, stop = block_bounds(text, block_id)
    return f"{text[:start]}\n\n{body}\n\n{text[stop:]}"


def vendored_bytes(block: dict) -> bytes:
    path = ROOT / block["vendored"]
    try:
        return path.read_bytes()
    except FileNotFoundError:
        fail(f'{block["id"]}: no vendored fragment at {block["vendored"]} — run an import')


def diff_report(block_id: str, expected: str, found: str) -> str:
    import difflib

    lines = list(
        difflib.unified_diff(
            expected.split("\n"),
            found.split("\n"),
            fromfile=f"{block_id} (pinned fragment)",
            tofile=f"{block_id} (SKILL.md block)",
            lineterm="",
            n=1,
        )
    )
    return "\n".join(f"    {line}" for line in lines[:40])


def do_check(pin: dict) -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    problems: list[str] = []
    for block in pin["blocks"]:
        raw = vendored_bytes(block)
        got = sha256(raw)
        if got != block["sha256"]:
            problems.append(
                f'  {block["id"]}: vendored {block["vendored"]} does not match the pin\n'
                f'    pin      {block["sha256"]}\n'
                f"    vendored {got}\n"
                "    The vendored bytes were edited, or the pin was changed without an import."
            )
            continue
        expected = render(block, raw)
        found = read_block(text, block["id"])
        if found != expected:
            problems.append(
                f'  {block["id"]}: the SKILL.md block does not match the pinned fragment\n'
                f"{diff_report(block['id'], expected, found)}\n"
                "    Generated text is not hand-edited: re-run compose, or fix it upstream."
            )
    if problems:
        sys.stderr.write("compose --check failed:\n" + "\n".join(problems) + "\n")
        raise SystemExit(1)
    ids = ", ".join(block["id"] for block in pin["blocks"])
    print(f'compose --check: {len(pin["blocks"])} block(s) match the pin ({ids})')


def do_import(pin: dict, source: Path) -> None:
    if not (source / ".git").exists():
        fail(f"{source} is not a git checkout — pass --source <ansvar-workflow-mcp>")
    commit = pin["commit"]

    manifest_raw = git_show(source, commit, UPSTREAM_MANIFEST)
    got = sha256(manifest_raw)
    if got != pin["manifest_sha256"]:
        fail(
            f"manifest sha256 mismatch at {commit[:12]}\n"
            f'  pin    {pin["manifest_sha256"]}\n'
            f"  actual {got}\n"
            "  The pin names a release that this checkout does not carry."
        )
    manifest = json.loads(manifest_raw)
    upstream = {entry["path"]: entry["sha256"] for entry in manifest.get("fragments", [])}

    text = SKILL_PATH.read_text(encoding="utf-8")
    for block in pin["blocks"]:
        path = block["path"]
        if path not in upstream:
            fail(f'{block["id"]}: {path} is not in the released manifest\'s fragments')
        raw = git_show(source, commit, path)
        got = sha256(raw)
        if got != upstream[path]:
            fail(f"{path}: bytes do not match the manifest ({got} != {upstream[path]})")
        if got != block["sha256"]:
            fail(
                f'{block["id"]}: manifest sha256 differs from the pin\n'
                f'  pin      {block["sha256"]}\n'
                f"  manifest {got}\n"
                "  Copy the manifest's hash into the pin deliberately — see the re-pin recipe."
            )
        out = ROOT / block["vendored"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        text = write_block(text, block["id"], render(block, raw))

    SKILL_PATH.write_text(text, encoding="utf-8")
    ids = ", ".join(block["id"] for block in pin["blocks"])
    print(f'compose: {len(pin["blocks"])} block(s) composed from {commit[:12]} ({ids})')
    print("compose: read the SKILL.md diff before committing — step 5 of the re-pin recipe")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compose SKILL.md over the pinned ansvar-workflow-mcp fragments.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify pin <-> vendored fragments <-> SKILL.md blocks; write nothing",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"ansvar-workflow-mcp checkout for an import (default: {DEFAULT_SOURCE})",
    )
    args = parser.parse_args()
    pin = load_pin()
    if args.check:
        do_check(pin)
    else:
        do_import(pin, args.source.resolve())


if __name__ == "__main__":
    main()
