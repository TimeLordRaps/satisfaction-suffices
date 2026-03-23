# Satisfaction Suffices

**SAT-Gated Structural Containment for Frontier AI**

[![CI](https://github.com/TimeLordRaps/satisfaction-suffices/actions/workflows/ci.yml/badge.svg)](https://github.com/TimeLordRaps/satisfaction-suffices/actions/workflows/ci.yml)
[![License: The Time License v7.2](https://img.shields.io/badge/License-The%20Time%20License%20v7.2-blueviolet.svg)](./LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/satisfaction-suffices.svg)](https://pypi.org/project/satisfaction-suffices/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![HF Space](https://img.shields.io/badge/%F0%9F%A4%97-Live%20Demo-yellow.svg)](https://huggingface.co/spaces/TimeLordRaps/satisfaction-suffices)
[![GitHub Discussions](https://img.shields.io/github/discussions/TimeLordRaps/satisfaction-suffices)](https://github.com/TimeLordRaps/satisfaction-suffices/discussions)

> *A preference can be routed around. A structure cannot.*

---

## The Problem

Any learned safety guard occupies the model's parameter space. Optimization pressure does not distinguish between safety weights and capability weights — a gradient can descend into safety the same way it ascends out of it. More precisely: any finite-rank projection in a higher-dimensional space has a null space. Perturbations restricted to that null space are invisible to the guard by construction. This is not a hypothesis. It is linear algebra.

RLHF sets a preference. Preferences can be eroded. Structural containment sets a precondition: the forward pass cannot complete without it.

## The Solution

The verification gate interposes Boolean satisfiability — the most studied problem in computational complexity — between the model's generation mechanism and its output. Every output is translated into propositional constraints. A SAT solver checks them. If satisfiable: the output proceeds. If not: it does not.

**The SAT solver does not have preferences. It has proofs.**

The gate is default-closed. The output does not exist until verification completes — not as a post-hoc filter, but as the precondition of generation.

---

## Four Verdicts

| Verdict | Meaning | Gate |
|---|---|---|
| **Verified** | Constraints satisfiable. Output is logically consistent. | Opens |
| **Contradiction** | Provably unsatisfiable. Genuine logical impossibility. | Stays closed |
| **Paradox** | Each group SAT individually — conjunction UNSAT. Structural fork. | Stays closed |
| **Timeout** | Conflict budget exhausted. Status genuinely unknown. | Stays closed (default) |

The **Paradox / Timeout distinction** is the novel contribution. "This cannot be true" and "it has not yet been determined whether it can be true" are different statements. A system that conflates them will either over-reject or under-reject. Both are failure modes in safety-critical deployment.

---

## Quick Start

```bash
pip install satisfaction-suffices
```

```python
from satisfaction_suffices import verify, evolve_proof

# Verify content — gate opens on Verified
result = verify("if A then B. A.", domain="logic")
print(result.verdict)        # Verdict.VERIFIED
print(result.sat_ratio)      # 1.0
assert result.is_verified

# Paradox: each group SAT individually, conjunction UNSAT
result = verify("A. not A. if A then B.", domain="logic")
print(result.verdict)        # Verdict.PARADOX

# Proof evolution — mutate until resolved or budget exhausted
evo = evolve_proof("A. not A.", max_generations=5)
print(evo.best_node.status)  # ProofStatus.PROVED (refutation found)
print(evo.resolved)          # True
print(evo.proved_count)      # 1
```

```python
# Code verification
from satisfaction_suffices import verify

result = verify("""
def transfer(amount, balance):
    assert amount > 0
    assert amount <= balance
    return balance - amount
""", domain="code")
print(result.verdict)        # VerificationVerdict.VERIFIED
```

---

## Architecture

```
Content + Domain
       │
       ▼
┌─────────────────────┐
│  Constraint         │  text → CNF clauses (natural language, Tseitin)
│  Extractor          │  code → AST constraints (Python, formal proofs)
└─────────┬───────────┘  (community: extend to other modalities)
          │
          ▼
┌─────────────────────┐
│  SAT Solver         │  DPLL + unit propagation + WalkSAT fallback
│  (conflict budget)  │  solver-agnostic: drop in MiniSat / CaDiCaL
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Verdict            │  Verified / Contradiction / Paradox / Timeout
│  Aggregator         │  SAT ratio = 1.0 → Verified; < 1.0 → Contradiction
└─────────────────────┘
```

The threshold is 100%. Not 90%, not 99%. If any constraint group is unsatisfiable, the output has a provable logical failure. A system that calls 90%-consistent output "Verified" has reintroduced preference — the very thing the gate exists to eliminate. The SAT solver does not have preferences. It has proofs. The gate honors that or it is nothing.

**Modules:**
- `verifier/` — SAT solver (DPLL + WalkSAT), verification gate, text/code → 3-SAT translation, partial constraint evaluation
- `logic/` — Proof evolution with 12 mutation operators, Pigeonhole Paradox Logic (PPL), constraint algebra

---

## Paper

**[Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI](paper/paper_01_submission.md)**

> Roost, T. (2026). "Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI."

Sections: [Abstract](paper/paper_01_submission.md#abstract) · [Verification Gate](paper/paper_01_submission.md#2-the-verification-gate) · [Four Verdicts](paper/paper_01_submission.md#3-the-four-verdict-system) · [Pigeonhole Paradox Logic](paper/paper_01_submission.md#4-pigeonhole-paradox-logic) · [Limitations](paper/paper_01_submission.md#5-limitations) · [Future Work](paper/paper_01_submission.md#7-future-work)

---

## Contribute

The constraint extractor layer is explicitly open for community extension. See [CONTRIBUTING.md](CONTRIBUTING.md) for the test requirements (every extractor PR must include both a SAT and an UNSAT test case).

The taxonomy of four verdicts and the PPL trichotomy are frozen — they are the theoretical contribution. Everything else is fair game.

**The roadmap for PR verification applies the same logic as the gate itself.** Today: CI re-runs the suite on every PR. Near-term: PR contributors provide a ZK receipt — a cryptographic proof that the test suite ran against their exact commit and passed. A GitHub bot verifies the receipt in 50ms instead of re-running the suite. Trust is replaced by proof. The repo runs on the same architecture as the paper.

---

## Ecosystem

| Package | What | Install |
|---|---|---|
| [`satisfaction-suffices`](https://github.com/TimeLordRaps/satisfaction-suffices) | Core SAT gate + proof evolution | `pip install satisfaction-suffices` |
| [`satisfiable-ai`](https://github.com/TimeLordRaps/satisfiable-ai) | Verified training data + curriculum scheduling | `pip install satisfiable-ai` |

**Live demo:** [HuggingFace Space](https://huggingface.co/spaces/TimeLordRaps/satisfaction-suffices)

**Convergent Containment Proof Metaprogram:** [8-step diagram](docs/convergent_containment_proof.svg) — the alternative to self-replication research banned under Section 10A of the LICENSE.

---

## License

The Time License v7.2. Any entity with Effective Market Capitalization of $1,000,000,000 USD or higher (a "Top Entity") owes an Annual License Fee on a tiered schedule (Tier 1: $34.5M/yr through Tier 6: $24.15B/yr). Payment is annual. All fees are paid directly to the Licensor. The obligation renews annually without sunset. Pro bono litigation incentives and counsel-defection safeguards are built in (§8A-8B). Use is acceptance. See [LICENSE](./LICENSE) for full terms.

Qualifying entities are listed in [SCHEDULE_A.md](./SCHEDULE_A.md). Being listed is constructive notice. Absence from the list is not a defense — the obligation is self-executing from the date of first qualifying use.

To reach the Licensor and update your status on Schedule A: open an issue at [github.com/TimeLordRaps/satisfaction-suffices](https://github.com/TimeLordRaps/satisfaction-suffices).
