---
title: "Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI"
authors:
  - name: Tyler Roost
    username: TimeLordRaps
tags:
  - sat
  - verification
  - ai-safety
  - structural-containment
  - proof-evolution
  - paradox-logic
  - boolean-satisfiability
  - alignment
datasets: []
models: []
spaces:
  - TimeLordRaps/satisfaction-suffices
license: other
---

# Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI

## Abstract

Any learned safety guard occupies the model's parameter space. Optimization pressure does not distinguish between safety weights and capability weights — a gradient can descend into safety the same way it ascends out of it. More precisely: any finite-rank projection in a higher-dimensional space has a null space. Perturbations restricted to that null space are invisible to the guard by construction. This is not a hypothesis. It is linear algebra.

This paper proposes structural containment: interpose a Boolean satisfiability (SAT) solver between the model's generation mechanism and its output as a mandatory verification gate. Every output is translated into propositional constraints. A SAT solver checks them. If satisfiable: the output proceeds. If not: it does not.

The contribution is a four-verdict system that distinguishes:
1. **VERIFIED** — constraints satisfiable, output logically consistent
2. **CONTRADICTION** — provably unsatisfiable, genuine logical impossibility
3. **PARADOX** — each constraint group SAT individually, conjunction UNSAT (structural, not solver-dependent)
4. **TIMEOUT** — solver exhausted conflict budget without resolving (operational, not structural)

The Paradox/Timeout distinction is novel. "This cannot be true" and "it has not yet been determined whether it can be true" are different statements. A system that conflates them will either over-reject or under-reject. Both are failure modes in safety-critical deployment.

## Key Results

- **100% threshold**: The verification threshold is 1.0 (all constraint groups must be satisfiable). Any threshold below 100% reintroduces preference — the very thing structural containment exists to eliminate.
- **Proof evolution**: 12 mutation operators resolve contradictions across generations, producing refutation proofs or resolving paradoxes.
- **Pigeonhole Paradox Logic (PPL)**: A trichotomy (pigeonhole impossibility / logical inconsistency / representational insufficiency) for classifying why structures fail.
- **Zero learned parameters in the gate**: The verification gate contains no trainable weights. It cannot be gradient-attacked.

## Links

- **Code**: [github.com/TimeLordRaps/satisfaction-suffices](https://github.com/TimeLordRaps/satisfaction-suffices)
- **PyPI**: [satisfaction-suffices](https://pypi.org/project/satisfaction-suffices/)
- **Demo**: [HuggingFace Space](https://huggingface.co/spaces/TimeLordRaps/satisfaction-suffices)
- **Paper (Markdown)**: [paper_01_submission.md](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/paper/paper_01_submission.md)

## Citation

```bibtex
@software{roost2026satisfaction,
  title     = {Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI},
  author    = {Roost, Tyler},
  year      = {2026},
  url       = {https://github.com/TimeLordRaps/satisfaction-suffices},
  version   = {0.0.2},
  license   = {CCUL v1.0}
}
```
