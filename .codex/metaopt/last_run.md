- What I inspected (high-level)
  - Existing experiment surface in `E:/satisfaction-suffices/scripts/`.
  - Current benchmark helpers in `E:/satisfaction-suffices/satisfiable_ai/benchmarks.py`.
  - Current test surface in `E:/satisfaction-suffices/tests/test_benchmarks.py`.

- What I chose + why (scores)
  - Chosen item: `Add phase-transition budget sweep experiment`.
  - Scores: impact=5, confidence=5, effort=2, risk=1, roi=12.5.
  - Why: it directly strengthens the repo's timeout-density claim by showing how the apparent peak changes as conflict budget changes.

- What I changed (files)
  - `E:/satisfaction-suffices/satisfiable_ai/benchmarks.py`
  - `E:/satisfaction-suffices/scripts/experiment_phase_transition_budget_sweep.py`
  - `E:/satisfaction-suffices/tests/test_benchmarks.py`

- What I ran (commands) and results
  - `./.venv/Scripts/python.exe -m pytest -q` -> passed, total coverage 92.67%.
  - `./.venv/Scripts/python.exe scripts/experiment_phase_transition_budget_sweep.py --n-vars 24 --n-instances 6 --budgets 40,80,160 --ratios 4.0,4.2,4.4,4.6 --json-out data/experiment_phase_transition_budget_sweep_smoke.json` -> passed.
  - Smoke result: budget 40 showed the strongest timeout peak at ratio 4.4 with density 16.7%; budgets 80 and 160 produced no timeouts on the same sampled band.

- Next suggestion(s)
  - Add a seed-stability sweep to test whether the 4.4-ish timeout peak persists across different RNG seeds.
  - If that holds, add an extractor-boundary paraphrase corpus so the repo has both solver-side and extractor-side evidence.
