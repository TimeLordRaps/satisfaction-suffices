#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from satisfaction_suffices.benchmarks import run_relevance_benchmarks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run task-relevant local benchmarks for the satisfiable-ai verifier."
    )
    parser.add_argument(
        "--profile",
        default="smoke",
        choices=("smoke", "full"),
        help="Benchmark profile to run.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write full benchmark results as JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_relevance_benchmarks(profile=args.profile)

    task = report["task_benchmarks"]
    phase = report["phase_transition"]

    print(f"Benchmark profile: {report['profile']}")
    print(
        f"Task proxy accuracy: {task['passed']}/{task['total']} "
        f"({task['accuracy']:.1%})"
    )

    print("\nVerdict suites:")
    for suite_name, suite in task["verdict"]["suites"].items():
        print(
            f"  - {suite_name}: {suite['passed']}/{suite['total']} "
            f"({suite['accuracy']:.1%})"
        )

    partial = task["partial"]
    print(
        f"\nPartial-prefix suite: {partial['passed']}/{partial['total']} "
        f"({partial['accuracy']:.1%})"
    )

    print("\nPhase-transition timeout density:")
    for row in phase["ratios"]:
        print(
            f"  - ratio={row['ratio']:.3f} sat={row['sat']:3d} "
            f"unsat={row['unsat']:3d} timeout={row['timeout']:3d} "
            f"timeout_density={row['timeout_density']:.1%}"
        )

    if phase["peak_timeout_ratio"] is not None:
        print(
            f"\nPeak timeout ratio: {phase['peak_timeout_ratio']:.3f} "
            f"({phase['peak_timeout_density']:.1%})"
        )

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"JSON report written to {args.json_out}")


if __name__ == "__main__":
    main()