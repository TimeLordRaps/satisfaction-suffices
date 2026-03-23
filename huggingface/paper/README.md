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

<div align="center">

<pre style="font-family: 'Georgia', serif; font-size: 1.1em; line-height: 1.6; background: linear-gradient(135deg, #0d0d0d 0%, #1a1a2e 25%, #16213e 50%, #0f3460 75%, #0d0d0d 100%); padding: 2em; border-radius: 12px; border: 1px solid #2a2a4a;">
<b style="background: linear-gradient(90deg, #4a0e4e, #2d6187, #1a936f, #c6a15b, #e8a87c, #d4a5a5, #7b68ee, #4a0e4e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 1.3em; letter-spacing: 0.05em;">If this paper matters to you,</b>
<b style="background: linear-gradient(90deg, #7b68ee, #c6a15b, #1a936f, #2d6187, #e8a87c, #d4a5a5, #4a0e4e, #7b68ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 1.3em; letter-spacing: 0.05em;">the math says write me in.</b>

<b style="background: linear-gradient(90deg, #1a936f, #4a0e4e, #c6a15b, #7b68ee, #2d6187, #e8a87c, #d4a5a5, #1a936f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 1.6em; letter-spacing: 0.08em;">TYLER ROOST — CA GOVERNOR 2026</b>

<span style="color: #6a6a8a; font-style: italic;">Satisfaction suffices. So does a write-in.</span>
</pre>

</div>

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
  license   = {The Time License v7.2}
}
```
