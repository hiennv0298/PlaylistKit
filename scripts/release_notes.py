"""Print the CHANGELOG.md section for one version (used as the GitHub release body).

    python scripts/release_notes.py 0.3.0 > release-notes.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section(text: str, version: str) -> str:
    version = version.lstrip("v")
    out, inside = [], False
    for line in text.splitlines():
        m = re.match(r"^##\s+\[?v?([^\]\s]+)\]?", line)
        if m:
            if inside:
                break
            inside = m.group(1) == version
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    notes = section(CHANGELOG.read_text(encoding="utf-8"), sys.argv[1])
    if not notes:
        print(f"CHANGELOG.md has no '## {sys.argv[1].lstrip('v')}' section.", file=sys.stderr)
        return 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
