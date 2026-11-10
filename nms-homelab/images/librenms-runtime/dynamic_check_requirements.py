#!/usr/bin/env python3
"""Read this installation's requirements.txt and preserve validator exit codes."""
from pathlib import Path
import sys
from requirement_validation import check

verbose = "-v" in sys.argv
path = Path(__file__).resolve().parent.parent / "requirements.txt"
try:
    # This LibreNMS file contains one PEP 508 requirement per line.
    requirements = [line.split("#", 1)[0].strip()
                    for line in path.read_text(encoding="utf-8").splitlines()]
    requirements = [line for line in requirements if line]
except OSError:
    print(f'WARNING: No requirements.txt file found as "{path}".')
    sys.exit(3)
if verbose:
    print("Required packages:", requirements)
sys.exit(check(requirements, verbose))
