#!/usr/bin/env python3
"""
SAT Gate — local-first verification gate.

Runs the full test suite via uv run pytest.
Writes proof_gate.json with a SHA-256 fingerprint of the run.
Blocks the commit if any test fails.

Usage (invoked by pre-commit hook automatically):
    uv run python scripts/sat_gate.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


PROOF_FILE = Path(__file__).parent.parent / "proof_gate.json"


def main() -> int:
    start = time.monotonic()
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "--tb=short"],
        capture_output=True,
        text=True,
    )
    elapsed = round(time.monotonic() - start, 2)

    output = result.stdout + result.stderr
    output_hash = hashlib.sha256(output.encode()).hexdigest()

    gate = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": elapsed,
        "exit_code": result.returncode,
        "output_hash": output_hash,
        "sat_verified": result.returncode == 0,
    }

    PROOF_FILE.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0:
        print(output)
        print(f"\n[SAT GATE] BLOCKED — tests failed. Fix before committing.")
        return 1

    print(
        f"[SAT GATE] VERIFIED — {elapsed}s  sha256:{output_hash[:16]}…"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
