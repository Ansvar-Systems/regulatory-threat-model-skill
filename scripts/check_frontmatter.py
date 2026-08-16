#!/usr/bin/env python3
"""Sanity-check SKILL.md's YAML frontmatter.

A skill file whose frontmatter does not parse is not a broken document — it is
an uninstallable one, and every consumer surface (claude.ai upload, the
ansvar.eu publish, the Lawve listing) discovers that separately and late. This
check is deliberately small: the frontmatter parses, it carries the keys the
consumers read, and its provenance block still agrees with the composition pin.

Usage: python3 scripts/check_frontmatter.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write("check_frontmatter: PyYAML is required (pip install pyyaml)\n")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = ROOT / "SKILL.md"
PIN_PATH = ROOT / "scripts" / "fragments.pin.json"
VERSION_RE = re.compile(r"^\d+\.\d+$")

problems: list[str] = []


def problem(message: str) -> None:
    problems.append(f"  {message}")


text = SKILL_PATH.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    sys.stderr.write("check_frontmatter: SKILL.md does not open with a --- frontmatter fence\n")
    raise SystemExit(1)
end = text.find("\n---\n", 3)
if end == -1:
    sys.stderr.write("check_frontmatter: SKILL.md frontmatter is never closed\n")
    raise SystemExit(1)

try:
    front = yaml.safe_load(text[4:end])
except yaml.YAMLError as exc:
    sys.stderr.write(f"check_frontmatter: frontmatter is not valid YAML: {exc}\n")
    raise SystemExit(1)

if not isinstance(front, dict):
    sys.stderr.write("check_frontmatter: frontmatter is not a mapping\n")
    raise SystemExit(1)

for key in ("name", "description", "license", "metadata"):
    if not front.get(key):
        problem(f'frontmatter is missing "{key}"')

metadata = front.get("metadata")
if not isinstance(metadata, dict):
    problem('"metadata" is not a mapping')
else:
    version = metadata.get("version")
    if not version:
        problem('metadata is missing "version"')
    elif not isinstance(version, str) or not VERSION_RE.match(version):
        problem(f'metadata.version "{version}" is not a quoted MAJOR.MINOR string')
    for key in ("author", "connector"):
        if not metadata.get(key):
            problem(f'metadata is missing "{key}"')

    # Provenance must not drift from the pin the generated blocks were composed
    # from: a re-pin that forgets the frontmatter publishes a file that misstates
    # where half its text came from.
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    composed = metadata.get("composed_from")
    if not isinstance(composed, dict):
        problem('metadata is missing the "composed_from" provenance block')
    else:
        if composed.get("repo") != pin["repo"]:
            problem(f'composed_from.repo "{composed.get("repo")}" != pin "{pin["repo"]}"')
        if composed.get("commit") != pin["commit"]:
            problem(f'composed_from.commit "{composed.get("commit")}" != pin "{pin["commit"]}"')
        declared = composed.get("fragments")
        if not isinstance(declared, dict):
            problem('composed_from is missing a "fragments" map of id -> sha256')
        else:
            expected = {block["id"]: block["sha256"] for block in pin["blocks"]}
            if declared != expected:
                problem(
                    "composed_from.fragments does not match the pin\n"
                    f"    frontmatter {declared}\n"
                    f"    pin         {expected}"
                )

if problems:
    sys.stderr.write("check_frontmatter failed:\n" + "\n".join(problems) + "\n")
    raise SystemExit(1)

print(f'check_frontmatter: SKILL.md frontmatter is valid (version {metadata["version"]})')
