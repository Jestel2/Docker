#!/usr/bin/env python3
"""Keep the legacy poller wrapper's PyMySQL check compatible with Python 3.14."""
import sys
from requirement_validation import check

sys.exit(check(["PyMySQL"], "-v" in sys.argv))
