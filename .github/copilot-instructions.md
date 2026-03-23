# satisfaction-suffices — Workspace Instructions

## What This Repo Is

A default-closed AI safety verification gate. Boolean SAT is interposed between a language model's forward pass and its output. The gate produces one of four verdicts: **Verified**, **Contradiction**, **Paradox**, or **Timeout**. The Paradox/Timeout distinction (structural impossibility vs. operational exhaustion) is the novel contribution.

**Paper:** `paper/paper_01_submission.md`  
**Package:** `src/satisfaction_suffices/`  
**License:** The Time License (see `LICENSE`) — custom commercial license, NOT open source. Do not reference it as CC BY, MIT, CCUL, or any other name. Line 1 of LICENSE is the name.

---

## Module Map

```
src/satisfaction_suffices/
├── __init__.py          — public API: verify(), evolve_proof(), Verdict enum, _LICENSE_NOTICE
├── bridge.py            — unified entry point bridging logic + verifier layers
├── logic/
│   ├── constraint.py    — ConstraintExtractor: text/code → propositional constraints
│   ├── ppl.py           — Pigeonhole Paradox Logic: structural contradiction detection
│   └── proof_evo.py     — ProofEvolution: incremental constraint refinement
└── verifier/
    ├── sat.py           — SATSolver: DPLL/CDCL core, conflict budget, timeout tracking
    ├── verify.py        — VerificationGate: orchestrates sat.py + constraint + ppl
    ├── partial.py       — PartialVerifier: streaming/partial constraint checking
    ├── text_to_3sat.py  — Text → 3-SAT clause transformer
    └── code_to_3sat.py  — Code → 3-SAT clause transformer
```

---

## The Four Verdicts

| Verdict | Meaning | Gate |
|---|---|---|
| `Verified` | Constraints SAT. Output is consistent. | Opens |
| `Contradiction` | Provably UNSAT. Logical impossibility. | Stays closed |
| `Paradox` | Each group SAT individually; conjunction UNSAT. Structural fork. | Stays closed |
| `Timeout` | Conflict budget exhausted. Status unknown. | Stays closed (default-closed) |

**Never conflate Paradox and Timeout.** They are structurally different. Any change that merges these two paths is a regression.

---

## Dev Rules

### Environment
- Python 3.10+, no external runtime dependencies (zero-dep package)
- Dev deps: `pytest>=8.0`, `pytest-cov>=5.0`
- Run with uv: `uv run pytest` or `uv run python`
- Local venv: `.venv/Scripts/python.exe` — use it, don't reach for system Python

### Running Tests
```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=satisfaction_suffices --cov-report=term-missing
```

### Building the Paper PDF
```bash
cd paper && make pdf   # requires pandoc + pdflatex
```

### Architecture Rules
1. **Default-closed**: the gate never opens on uncertainty. Timeout = closed. Unknown = closed.
2. **Zero runtime dependencies**: `satisfaction_suffices` imports only stdlib. No numpy, no pysat, no external solvers in the shipped package.
3. **Verdicts are an enum** — `Verdict.VERIFIED`, `Verdict.CONTRADICTION`, `Verdict.PARADOX`, `Verdict.TIMEOUT`. Never use raw strings.
4. **The Paradox/Timeout split is not optional.** It is the paper's contribution. Any abstraction that collapses them violates the spec.
5. **Fail loud** — no `try: import X; except: pass`. No swallowed exceptions. Let errors propagate.
6. **No sys.path hacks.** The package is installed via `pip install -e .` — use the import path.

### What NOT to Do
- Do not add runtime dependencies to `pyproject.toml [project] dependencies`
- Do not create a parallel `Verifier` class — extend the existing `VerificationGate`
- Do not rename `Verdict` enum members — they are part of the public API
- Do not add a "graceful degradation" path that defaults to Verified on error — that inverts the safety model
- Do not call the license "CCUL v1.0", "CC BY 4.0", or anything other than "The Time License"

---

## Public API (stable)

```python
from satisfaction_suffices import verify, evolve_proof, Verdict

result = verify("if A then B. A.", domain="logic")
result.verdict          # Verdict enum
result.sat_ratio        # float 0.0–1.0
result.is_verified      # bool
result.explanation      # str
result.clauses          # list of constraint clauses
result.conflicts        # int (solver conflict count)

evolved = evolve_proof(result, new_evidence="C implies D")
evolved.verdict         # Verdict (may differ from original)
```

---

## HuggingFace Space

Live demo: `huggingface/space/` — `app.py` is a Gradio app.  
Paper card: `huggingface/paper/` — BibTeX + abstract for HF paper page.  
These files are kept in sync with the paper. If you update the abstract or citation, update both.

---

## DOI / Citation

No DOI yet. The Zenodo GitHub integration is enabled — a DOI will be issued on the first GitHub Release.  
After the release, add to `CITATION.cff`:
```yaml
doi: 10.5281/zenodo.XXXXXXX
```
And add the Zenodo DOI badge to `README.md`.

---

## Paper Text vs. Code

The paper (`paper/paper_01_submission.md`) describes the architecture. If you change behavior in the code, check whether the paper's description still matches. The paper is the spec; the code is the implementation.
