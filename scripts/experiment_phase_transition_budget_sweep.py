#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from satisfiable_ai.benchmarks import run_phase_transition_budget_sweep


def _parse_int_csv(text: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in text.split(",") if part.strip())


def _parse_float_csv(text: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in text.split(",") if part.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep SAT solver budgets across the 3-SAT phase-transition band."
    )
    parser.add_argument("--n-vars", type=int, default=40)
    parser.add_argument("--n-instances", type=int, default=16)
    parser.add_argument(
        "--budgets",
        type=_parse_int_csv,
        default=(40, 80, 160, 320),
        help="Comma-separated solver conflict budgets.",
    )
    parser.add_argument(
        "--ratios",
        type=_parse_float_csv,
        default=(3.8, 4.0, 4.2, 4.267, 4.4, 4.6),
        help="Comma-separated clause/variable ratios to probe.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("data/experiment_phase_transition_budget_sweep.json"),
        help="Path to write the full JSON report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_phase_transition_budget_sweep(
        n_vars=args.n_vars,
        n_instances=args.n_instances,
        budgets=args.budgets,
        ratios=args.ratios,
        seed=args.seed,
    )

    print(
        f"Budget sweep: n_vars={report['n_vars']} "
        f"n_instances={report['n_instances']} budgets={list(report['budgets'])}"
    )
    for run in report["runs"]:
        peak_ratio = run["peak_timeout_ratio"]
        peak_density = run["peak_timeout_density"]
        peak_label = "none" if peak_ratio is None else f"{peak_ratio:.3f} ({peak_density:.1%})"
        print(
            f"  - budget={run['budget']:>4} total_timeouts={run['total_timeouts']:>3} "
            f"mean_timeout_density={run['mean_timeout_density']:.1%} peak={peak_label}"
        )

    if report["strongest_peak_budget"] is not None:
        print(
            f"\nStrongest peak budget: {report['strongest_peak_budget']} at ratio "
            f"{report['strongest_peak_ratio']:.3f} ({report['strongest_peak_density']:.1%})"
        )

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"JSON report written to {args.json_out}")


if __name__ == "__main__":
    main()