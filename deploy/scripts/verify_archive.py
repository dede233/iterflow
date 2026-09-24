"""Refuse traversal, links and special files before an uploads archive is restored."""

import sys
import tarfile
from pathlib import Path

archive = Path(sys.argv[1])
with tarfile.open(archive, "r") as stream:
    for member in stream:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
            raise SystemExit(f"unsafe uploads archive member: {member.name!r}")
