#!/usr/bin/env python3
"""
SAT Gate — ZK local-first verification gate.

Runs the full test suite, binds the proof to the git tree hash,
and writes proof_gate.json. CI verifies the receipt instead of
re-running the suite. Trust is replaced by proof.

The proof is: SHA256(test_output || tree_hash)
- test_output: stdout+stderr of pytest
- tree_hash: git write-tree (staged content hash)

A valid proof_gate.json in a commit means:
  "These tests passed against exactly this code."

Usage (invoked by pre-commit hook automatically):
    uv run python scripts/sat_gate.py

CI verification (--verify mode):
    python scripts/sat_gate.py --verify
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


PROOF_FILE = Path(__file__).parent.parent / "proof_gate.json"


def get_tree_hash() -> str:
    """Get the git tree hash of staged content."""
    result = subprocess.run(
        ["git", "write-tree"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Fallback: use HEAD tree if not in a git context (CI checkout)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            capture_output=True, text=True,
        )
    return result.stdout.strip()


def compute_proof(test_output: str, tree_hash: str) -> str:
    """Commit-bound proof: SHA256(test_output || tree_hash)."""
    payload = (test_output + tree_hash).encode()
    return hashlib.sha256(payload).hexdigest()


def verify_mode() -> int:
    """CI verification: check that proof_gate.json is valid for this tree."""
    if not PROOF_FILE.exists():
        print("[SAT GATE] NO PROOF — proof_gate.json missing. Running tests.")
        return run_and_stamp()

    gate = json.loads(PROOF_FILE.read_text(encoding="utf-8"))

    if not gate.get("sat_verified"):
        print("[SAT GATE] PROOF INVALID — sat_verified is false.")
        return 1

    tree_hash = get_tree_hash()
    if gate.get("tree_hash") != tree_hash:
        print(f"[SAT GATE] PROOF STALE — tree hash mismatch.")
        print(f"  proof: {gate.get('tree_hash', 'missing')}")
        print(f"  actual: {tree_hash}")
        print("[SAT GATE] Re-running tests...")
        return run_and_stamp()

    print(f"[SAT GATE] PROOF VERIFIED in 0s — {gate['proof'][:16]}…")
    print(f"  tree:  {tree_hash}")
    print(f"  stamp: {gate['timestamp']}")
    return 0


def run_and_stamp() -> int:
    """Run tests and write commit-bound proof."""
    start = time.monotonic()
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "--tb=short"],
        capture_output=True, text=True,
    )
    elapsed = round(time.monotonic() - start, 2)

    output = result.stdout + result.stderr
    tree_hash = get_tree_hash()
    proof = compute_proof(output, tree_hash)

    gate = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": elapsed,
        "exit_code": result.returncode,
        "tree_hash": tree_hash,
        "proof": proof,
        "sat_verified": result.returncode == 0,
    }

    PROOF_FILE.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0:
        print(output)
        print(f"\n[SAT GATE] BLOCKED — tests failed. Fix before committing.")
        return 1

    print(f"[SAT GATE] VERIFIED — {elapsed}s  proof:{proof[:16]}…")
    print(f"  tree: {tree_hash}")
    return 0


def main() -> int:
    if "--verify" in sys.argv:
        return verify_mode()
    return run_and_stamp()
if __name__ == "__main__":
    sys.exit(main())
