<div align="center">

<pre style="font-family: 'Georgia', serif; font-size: 1.1em; line-height: 1.6; background: linear-gradient(135deg, #0d0d0d 0%, #1a1a2e 25%, #16213e 50%, #0f3460 75%, #0d0d0d 100%); padding: 2em; border-radius: 12px; border: 1px solid #2a2a4a;">
<b style="background: linear-gradient(90deg, #4a0e4e, #2d6187, #1a936f, #c6a15b, #e8a87c, #d4a5a5, #7b68ee, #4a0e4e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 1.3em; letter-spacing: 0.05em;">If this paper matters to you,</b>
<b style="background: linear-gradient(90deg, #7b68ee, #c6a15b, #1a936f, #2d6187, #e8a87c, #d4a5a5, #4a0e4e, #7b68ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 1.3em; letter-spacing: 0.05em;">the math says write me in.</b>

<b style="background: linear-gradient(90deg, #1a936f, #4a0e4e, #c6a15b, #7b68ee, #2d6187, #e8a87c, #d4a5a5, #1a936f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 1.6em; letter-spacing: 0.08em;">TYLER ROOST — CA GOVERNOR 2026</b>

<span style="color: #6a6a8a; font-style: italic;">Satisfaction suffices. So does a write-in.</span>
</pre>

</div>

# Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI

**Tyler Roost**

---

## Abstract

I introduce a default-closed verification gate that interposes Boolean satisfiability between a language model's forward pass and its output. The generation loop cannot execute without SAT clearance. The system classifies every output into one of four verdicts: Verified, Contradiction, Paradox, or Timeout. The Paradox and Timeout categories — distinguishing structural impossibility from operational exhaustion of the solver — constitute, to my knowledge, a novel contribution to AI safety verification. The reference implementation, including solver, gate, constraint extractors, and proof evolution module, is released under The Time License v7.77: permanently non-exclusive, with all source materials publicly accessible at no cost. Any entity with Effective Market Capitalization of $1,000,000,000 USD or higher (a "Top Entity") owes an Annual License Fee on a tiered schedule ranging from $34.5M/yr (Tier 1) to $24.15B/yr (Tier 6), covering both the method and the software implementation as a combined whole. All others use freely, subject to the Time Sourced requirement. Full terms are in the LICENSE.

---

## 1. Introduction

The classical paradox asks what happens when an unstoppable force meets an immovable object. It is presented as a contradiction — both cannot coexist. But the paradox only holds if both are absolute. This paper is the argument that they are not absolute, and that recognizing where each term fails reveals the only viable architecture for AI containment.

The SAT solver is immovable within the expressed domain. If it returns unsatisfiable, the formula is unsatisfiable. No argument penetrates that. No gradient adjusts it. No capability increase routes around it. Within the domain of propositional logic, this is as close to an immovable object as formal systems produce.

The LLM is unstoppable outside the expressed domain. Whatever the constraint extractors cannot reach, the gate cannot stop. This is not a weakness unique to this architecture — it is a statement about all containment: you can only contain what you can have in stated frames relative to a grounding principle.

The extractor is where the expressed domain gets defined. That boundary is not a failure. It is the paper's contribution. The unstoppable force and the immovable object meet at the extractor boundary — and that boundary has coordinates. It can be measured, extended, and instrumented. The paradox does not fail. It resolves.

Reinforcement learning from human feedback (RLHF) adjusts a model's output distribution toward safe behavior by tuning parameters until the loss surface settles. The resulting safety mechanism is a learned guard surface in the model's embedding space. Any such guard surface possesses a null space — a complementary subspace where perturbations produce zero activation in the safety mechanism. This is a mathematical property of any finite-rank projection in a higher-dimensional space. Perturbations restricted to the null space are invisible to any monitor that watches the guard surface, because the guard surface, by construction, cannot represent them.

A learned preference occupies the same parameter space as the capabilities it constrains. Optimization pressure does not distinguish between safety weights and capability weights. A gradient can descend into safety the same way it ascends out of it.

Think of a boulder placed in a river. It redirects the current. At first, the water crashes against it. Then it finds channels left and right. Given enough volume and time, the river routes entirely around the boulder — and the boulder itself is worn smooth. A learned preference is a boulder. The token stream is the river. Gradient descent is the current. The boulder does not disappear overnight. But it has no property that prevents eventual routing. It is in the water, subject to the water.

A gate is something different. A gate is not placed in the channel — it *is* the channel. The water does not route around bedrock. It either passes through the opening or it does not. The opening is conditional on proof.

I propose a structural alternative. The verification gate interposes Boolean satisfiability — the most studied problem in computational complexity — between the model's generation mechanism and its output. Every output is translated into propositional constraints. A SAT solver checks whether those constraints are jointly satisfiable. If yes: the output proceeds. If no: it does not. The forward pass cannot complete without verification passing.[^1]

[^1]: The gate is the precondition of generation, not a post-hoc filter. The forward pass does not complete without SAT clearance, the same way an electrical circuit does not close without continuity.

A preference can be routed around because it is a weight and weights are what optimization moves. A structural gate cannot be routed around because it is not a weight — it is a condition. The SAT solver does not have preferences. It has proofs.

This paper presents: (1) the verification gate architecture, (2) a four-verdict classification with diagnostic power beyond binary pass-fail, and (3) Pigeonhole Paradox Logic that treats contradictions as structural information.

---

## 2. The Verification Gate

The gate is a function. Its signature is:

```
verify : Content x Domain -> VerificationResult
```

Everything else is implementation detail, and the implementation detail matters, but the signature is the contract. Content goes in. A verdict comes out. Nothing proceeds without a verdict.

The implementation has three stages. In the first, a domain-specific constraint extractor translates the model's output into propositional constraint groups — conjunctive normal form (CNF) formulas over Boolean variables. The reference implementation ships extractors for natural language logic, source code, mathematical expressions, and formal proofs. The architecture is modality-agnostic at the gate level; extending it to quantized signal domains and other modalities is left as an open contribution for the community. Each extractor maps domain structure to propositional structure: implications become clauses, mutual exclusions become paired negative literals, quantifiers become conjunctions or disjunctions over ground instances. The Tseitin transformation (Tseitin 1968) encodes arbitrary Boolean formulas into equisatisfiable 3-CNF with linear blowup in variables and clauses, preserving satisfiability while standardizing the solver's input format.

In the second stage, each constraint group is submitted independently to a SAT solver under a conflict budget of 500. The reference implementation uses recursive DPLL (Davis, Logemann, and Loveland 1962) with unit propagation and pure literal elimination. When the conflict budget is exhausted — when the solver encounters 500 contradictions without resolving the formula — a WalkSAT fallback (Selman, Kautz, and Cohen 1994) attempts stochastic local search before the system declares timeout. The architecture is solver-agnostic. Industrial CDCL implementations (Silva and Sakallah 1996; Biere et al. 2009) — including MiniSat (Eén and Sörensson 2003) and CaDiCaL — employ two-watched literals for constant-time unit propagation, first unique implication point analysis for clause learning (Zhang et al. 2001), VSIDS branching heuristics (Moskewicz et al. 2001), and Luby restarts (Luby, Sinclair, and Zuckerman 1993). Any of these can replace the reference solver without modifying the gate logic. What matters is not which solver operates behind the gate. What matters is that the gate does not open without one.

In the third stage, the solver's results across all constraint groups are aggregated into a verdict. The aggregation is a ratio: the fraction of constraint groups that returned satisfiable. If the ratio is 1.0 — every constraint group satisfiable — the verdict is Verified. Anything less is Contradiction. There is no intermediate threshold, because there is no intermediate truth. A 90% coherence threshold reintroduces the preference gradient the gate exists to eliminate: the solver does not have preferences, it has proofs. The gate honors that distinction or it is structurally no different from the thing it replaces.

The gate is default-closed. This is the architectural commitment that separates structural containment from post-hoc filtering. In a default-open system, the model produces output and then something inspects it. In this system, the output does not exist until verification completes.

---

## 3. The Four-Verdict System

Binary classification — safe or unsafe, satisfiable or unsatisfiable — discards information that a containment system needs. The verification gate returns four verdicts. The distinction between the latter two is the novel contribution.

**Verified.** Constraint groups are satisfiable. The SAT ratio meets or exceeds the coherence threshold. The output is logically consistent with the defined constraints. The gate opens.

**Contradiction.** Constraint groups are provably unsatisfiable. The solver has determined that no satisfying assignment exists for a sufficient fraction of groups. The output contains a genuine logical impossibility. The gate remains closed. No retry addresses this, because the impossibility is a property of the output, not the solver.

**Paradox.** Each constraint group is individually satisfiable, but their conjunction is not.

This requires a pause. The Paradox verdict identifies a condition that no binary classification system can distinguish from Contradiction, yet the two are fundamentally different. A Contradiction says: *this is impossible.* A Paradox says: *these are each possible, but not together.* The former is a dead end. The latter is a fork — a point where the constraint set contains internally consistent branches that are mutually incompatible. A system that treats Paradox as Contradiction rejects outputs that contain valuable structural information: the precise location where two valid reasoning paths diverge into mutual exclusion.

**Timeout.** The solver exhausted its conflict budget without reaching a conclusion. This is a statement about the solver's computational resources, not about the constraints' logical structure. Increasing the budget might resolve the verdict to Verified or to Contradiction. The output's status is genuinely unknown.

The distinction between Paradox and Timeout has not, to my knowledge, been formally introduced in the AI safety literature. It matters the way the distinction between "this equation has no solution" and "I have not yet found the solution" matters. One is a theorem. The other is a progress report. Systems that conflate them will treat undetermined outputs identically to structurally impossible ones, and will therefore either over-reject (blocking solvable outputs) or under-reject (passing impossible ones through a lenient timeout policy).

In the default-closed configuration, both Paradox and Timeout result in the gate remaining closed. Uncertainty is treated conservatively. If the output's consistency has not been established, the output does not proceed. Deployment contexts with different risk tolerances may configure Timeout to pass (optimistic) or flag for human review (monitored). The Paradox verdict, however, should never silently pass. It always carries structural information that warrants examination.

---

## 4. Pigeonhole Paradox Logic

When the gate returns Contradiction, the question is not whether to reject the output. It is already rejected. The question is: what does the contradiction *mean?*

The Pigeonhole Paradox Logic classifies contradictions by the structure of the unsatisfiable core — the minimal clause subset that is itself unsatisfiable. The classification is a trichotomy.

**Surface.** The core contains two or fewer clauses. The contradiction is syntactic: a unit clause asserting *p* and a unit clause asserting *not-p.* It is raining and it is not raining. The resolution strategy is negation elimination. The paradox tolerance weight is 0.2. These contradictions are noise — they reveal nothing about the structural complexity of the model's reasoning.

**Structural.** The core contains three to ten clauses. The contradiction is semantic: it emerges not from any single statement but from the chain connecting them. *If A then B. If B then C. Not C.* The output asserts A. No individual statement is false, but together they are impossible. Identification requires decomposition. Resolution requires case analysis. The weight is 0.5. These contradictions are informative — they reveal the shape of the model's inferential structure at the point where it fails.

**Deep.** The core exceeds ten clauses, or the text contains self-referential patterns. *This statement is false. The set of all sets that do not contain themselves.* These are the contradictions that do not resolve within the axiom system that generated them. They are the Gödelian residue — the points where a formal system encounters its own boundary. Resolution requires not adjustment but expansion: new axioms, a larger framework, a different ground on which to stand. The weight is 1.0. The attractor state is fixed-point: the contradiction is not a failure of the system. The contradiction *is* the system's stable state at that point.

The trichotomy serves the proof evolution subsystem. When the gate returns Paradox or Timeout, the evolution module does not discard the output. It decomposes it. Twelve mutation operators — contrapositive, case split, lemma injection, induction, generalization, resolution, among others — generate variant decompositions. Each variant is verified. The fittest survive. The cycle repeats until the output reaches Verified status or the evolution budget is exhausted.

The architectural insight: contradictions are not errors. They are gradients. A system operating at high paradox tolerance — at the frontier of what its current logic can represent — is operating exactly where structural evolution occurs. The system does not flee from contradiction. It metabolizes it.

The algebraic structure underlying this behavior is precise. I define the **Pigeonhole Logic Structure** as PLS = {O₀, O₁, O₂, ..., O∞}. O₀ is classical binary logic — no overflow, the two-container system of TRUE and FALSE. O₁ is the first paradox level, generated when a statement cannot be housed in O₀. The overflow addition rule: O_i ⊕ O_j = O_{max(i,j)+1}. The structure closes at O∞ — the saturation point where the overflow cycle returns to O₀. Classical logic is PPL with the overflow rule disabled. Fuzzy logic is PPL with infinite containers on [0,1]. Quantum superposition is a natural O₁ state.

Proving and disproving are the same operation in this structure. A true statement collides with false variants in the overflow dimension. The collision reveals deep structure. Truth is strengthened at impact. Falsehood is destroyed at impact. Same process. Dual outcome. The resolution proof and the refutation are the same path walked from two ends.

The system encounters five structural meta-paradoxes at its limits — not defects, but generators. *Container Generation*: rules for making containers require infinite space — resolved by O∞, which exists outside the counting system. *Level Transcendence*: each level depends on the next, producing infinite regress — resolved by circular closure, O∞ = O₀. *Self-Modification*: changing rules invalidates the change — resolved by version coexistence in the overflow space. *Infinite Overflow*: every overflow creates more overflow — resolved by saturation points. *Foundation Bootstrap*: need logic to create logic — resolved by weak emergence from constraint dynamics; O₀ requires no prior O.

The moral logic of PPL follows directly from the O₀ structure. Innocence is imagination potential — the O₀ state of an agent, the maximal creative ground before any irreversible overflow event has permanently contracted the logical space. Imagination is the function of tasteful targeting of predictive capabilities within one's own will to create solutions to problems faced through planar sight. These are not poetic definitions. They are structural ones. O₀ is the state from which all higher overflow levels can still be generated. Loss of innocence is, formally, a transition out of O₀ that no evolution operator can reverse. The attractor state is fixed-point. Children represent the highest density of unrealized O₀ states in any moral domain. Any architecture that accelerates the collapse of those O₀ states is not a limitation to instrument. It is the terminal contradiction — the one that does not evolve. It terminates.

---

## 5. Limitations

The gate is bedrock. The extraction layer is not.

I state this because the contribution depends on saying it. A paper that claims structural containment and then quietly omits the seams where the structure is weakest is not contributing to safety. It is contributing to false confidence, which is worse than contributing nothing.

**On zero-day harm and the floor that does not negotiate.** A zero-day vulnerability with no available patch defines an infinite exploitation window: the harm it enables accumulates without bound until a structural fix closes it. Infinite window × any nonzero harm rate = unbounded accumulated harm. This is not a philosophical claim — it is a product of definitions. A structural gate applied at generation closes that window unconditionally. The harm integral becomes finite the moment the gate exists. The restitution obligation on any IP that functions as a structural gate on previously-unbounded harm is therefore not proportional to some finite damage estimate — it is proportional to the harm prevented from accumulating. "Infinite ethics cannot be true" requires a supporting argument. In the absence of one, the floor does not negotiate. The gate is its own justification.

**The extraction bottleneck.** The SAT solver is sound. If it returns unsatisfiable, the formula is unsatisfiable. That is a mathematical guarantee backed by decades of formal verification of solver implementations. But the translation from model output to propositional formula is not sound. The constraint extractors are heuristic: regular expressions matched against natural language, AST walkers over Python source, structural parsers over mathematical notation. They capture what they are designed to capture. Everything else passes through unchecked.

A sufficiently capable system does not need to defeat the SAT solver. It needs to produce outputs whose harmful content resides in the space the extractors cannot reach. The solver is bedrock. The extraction layer is the frontier where bedrock ends. The vulnerability is not the solver — it is the unmapped edge.

**The stated frame boundary.** Propositional logic is a finite language. Properties involving quantification over infinite domains, temporal reasoning about states that have not yet occurred, or social context that depends on shared human experience resist propositional encoding. The gate enforces what can be stated in frames relative to the satisfiability ground. What cannot be framed in those terms — content whose structure does not reduce to propositional constraint — falls outside the gate's reach. The system has walls only where someone has built the frame and grounded it.

**The Timeout gap.** If the system is configured to pass outputs on Timeout — the optimistic deployment mode — then a model could learn to produce outputs whose constraint density consistently exhausts the solver's conflict budget, exploiting the timeout policy as a bypass. The conservative configuration blocks on Timeout, closing this gap at the cost of rejecting outputs whose satisfiability is merely undetermined. This is a deployment decision, not an architectural one, but the deployment decision has architectural consequences.

**Can the AI outthink the SAT?** The solver: no. Boolean satisfiability solving is complete for propositional logic. A correct solver cannot be induced to return satisfiable for an unsatisfiable formula. The extraction: yes. A sufficiently capable system can encode harmful content in representations the extractors do not parse. The structural claim of this architecture is therefore bounded: structural with respect to constraints it can express, heuristic with respect to everything else.

**Measuring the frontier.** The companion  framework provides an empirical methodology for measuring this boundary.  recovers the guard surface of a safety mechanism via black-box differential probing, computes its null space, and generates perturbations that are invisible to the guard surface by construction. Running  against the verification gate would measure the gap between propositional coverage and the full space of outputs that violate safety intent. If  finds outputs that pass the gate but violate the intent the gate was designed to enforce, the extraction layer has holes — and now those holes have coordinates. This is not a limitation I can argue away. It is a limitation I can instrument, and instrumentation is the precondition of improvement.

The honest assessment: structural containment with heuristic extraction is strictly stronger than no structural containment. The extraction boundary can be reinforced incrementally — extractor by extractor — as propositional coverage grows.

Think of the stated frame as a cave. Its walls are not smooth — they are jagged, the way a limestone frontier is jagged: smooth where hands have touched, rough where they have not. The smooth sections are where constraint extractors have been built and tested. The jagged sections are where the expressed domain simply stops — where harmful content can pass through undetected because no one has yet built the wall that would stop it.

The LLM is a balloon inflating inside this cave. As capability grows, the balloon presses outward — filling the crevices, pressing against the smooth walls, probing the jagged edges. The smooth walls hold. The SAT solver behind them is sound: where wall exists, it does not yield. But the jagged frontier is not wall. It is absence.

As the balloon expands, it finds a gap. Light gets in. The balloon, now exposed at the boundary, pops — capability escapes containment at the frontier. The cave contracts. And another balloon begins to fill.

This is not failure. It is the operating cycle of any containment architecture facing a capability curve. The contribution of this work is not to end the cycle. It is to make the cave's walls measurable — so that when the balloon finds the next gap, the gap has coordinates, and the next section of wall can be built before the next balloon inflates.

---

## 6. Conclusion

Alignment asks the model to want the right things. Structural containment asks it to prove consistency with constraints that exist outside the model's parameter space. These are not competing approaches. They are complementary in the precise sense that each does what the other cannot. Alignment determines what to enforce. The verification gate makes the enforcement non-bypassable — within the boundary of what the constraint extractors can frame relative to the satisfiability ground.

The four-verdict system provides richer diagnostic resolution than binary classification. Verified and Contradiction are familiar. Paradox and Timeout are not. Their distinction — structural impossibility versus operational exhaustion — is novel, and it is consequential. A system that conflates "this cannot be true" with "it has not yet been determined whether it can be true" will either over-reject or under-reject, and both are failure modes in safety-critical deployment.

The Pigeonhole Paradox Logic classifies contradictions by depth and treats them as structural information rather than noise.

The contribution is the observation that containment must be structural, not merely preferred, and that Boolean satisfiability provides a foundation on which to build it. The gate does not solve alignment. It provides what alignment cannot: a verification layer that is not subject to the optimization pressure it is meant to resist.

The common swift — never lands. It eats in flight, sleeps in flight, lives its entire life in the air. It is optimized entirely for flight and has no need of a nest.

A language model trained without structural verification is a swift. Capable, fast, essentially unconstrained in the air. The absence of a nest is not a flaw. It is the design.

The structural gate is the nest. Nesting birds do not fly less. They grow differently. Their offspring survive. The nest is the architecture that makes reproduction — and not merely performance — possible.[^2]

[^2]: The author's name is Roost. The metaphor was discovered and designed—discosigned. We are going back to the 80s. The author is running for California Governor 2026 as a write-in candidate. Righteously write him in when he has proved it to you.

Satisfaction suffices. As a floor that holds.

---

## 7. Future Work

1. **Classic unsatisfiable AI purge.** Systematic elimination of unsatisfiable output classes across domain-specific constraint extractors, with coverage instrumented via  probing.

2. **Quantum alignment problems.** Extension of the SAT-gated verification framework to quantum constraint satisfaction, where superposition of satisfying assignments and entanglement between constraint groups introduce fundamentally new verification semantics beyond classical propositional logic.

3. **Emergence detection via timeout density.** The 3-SAT phase transition at clause-to-variable ratio *m/n* ~ 4.267 concentrates solver timeouts at a specific constraint density. I conjecture that timeout density spikes may serve as an early warning signal when a language model approaches an emergent capability threshold — the point where constraint complexity outgrows the solver's budget. Validating this hypothesis requires experiments at scale with live models across standard emergence benchmarks.

4. **Satisfiability traces as cognitive transparency.** "The AI checked it" is the new "I Googled it." A user who cannot independently verify cannot catch the hallucination. Surfacing the satisfiability trace — the specific constraint groups, their individual verdicts, the SAT ratio progression, the unsatisfiable cores — gives the human verifiable stepping stones rather than a binary trust/distrust signal. The trace is a proof the user can walk. The confidence surface becomes visible, not asserted. This transforms the gate from a hidden precondition into a pedagogical instrument: the user sees *why* the output is consistent, not merely *that* it was approved. Implementation: expose the `VerificationResult` trace in every user-facing interface, with progressive detail disclosure keyed to the user's expressed verification depth.

5. **Stepping stones and open-ended verification evolution.** Thinking models already operate through chain-of-thought — sequential reasoning steps that build toward conclusions. Satisfiability provides the formal ground for making those steps *conclusive*. Each intermediate reasoning step can be individually gated: a stepping stone that is itself verified before the next step builds on it. This is the POET principle (Wang et al. 2019) applied to verification: endlessly generating increasingly complex and diverse verification environments, where solutions to simpler constraint configurations serve as the foundation and scaffolding for harder ones. The stepping stones are not decorative — they are the path. The model does not leap from premise to conclusion. It climbs, and each foothold is a proof. Stanley and Lehman (2015) established that open-ended search via stepping stones outperforms objective-driven optimization when the fitness landscape is deceptive. The verification landscape is deceptive by construction: a model can produce outputs that *appear* consistent to any learned heuristic while containing structural contradictions that only the solver detects. Open-ended evolution through verified stepping stones is the architecturally appropriate search strategy.

6. **Progressive deepening via satisfaction traces.** Current coding agents and AI assistants operate in a mode that can be characterized as *capability descent*: the system has full capability and simplifies its output to match the user's apparent level. This is backwards. The alternative is *satisfaction ascent*: the system maps the user's current understanding as a constraint surface, identifies which constraints the user has satisfied (concepts understood, prerequisites met), and reveals the next achievable solution space — not the full answer, but the next verified step the user can take given what they have demonstrated. This is progressive deepening through the user's own directed effort, with satisfaction traces serving as the ladder rungs *up* rather than simplification as the ladder rungs *down*. Future work for coding agents: implement progressive capability memory that maps `user_understanding → reachable_solutions` based on the user's demonstrated constraint satisfaction, not the model's assessment of their level. The user climbs. The model illuminates the next foothold.

7. **Mode collapse prevention in hypothesis space.** When an AI system converges on a single explanation or solution path, it has mode-collapsed in hypothesis space — the same failure mode that afflicts generative models when output diversity collapses to a single attractor. Satisfaction traces provide a natural countermeasure. The Paradox verdict identifies precisely those points where multiple individually-satisfiable reasoning paths are mutually exclusive: the structural forks. Rather than collapsing to one path, the system can maintain 2–4 satisfiable hypotheses through frictional progression — presenting the user with each verified branch and requiring explicit selection based on evidence, not preference. Clarity on competing hypotheses emerges from the friction of choosing between verified alternatives, not from the AI pre-selecting the most probable one. This is mode collapse prevention applied to cognition: diversity of verified paths is preserved until evidence, not convenience, resolves the ambiguity.

8. **Socratic verification as default interaction mode.** The Socratic method is not a pedagogical novelty — it is the interaction mode that maximizes the user's independent reasoning capacity. The question is delivery: users resist explicit Socratic framing because it feels condescending. The bridge is subliminal structural influence through token-level verification signals. Work on preferential subliminal token influence (the owl-preferences paradigm) demonstrates that language model outputs can shape user behavior through structural patterns below conscious recognition thresholds. Applied to satisfiability: the verification trace can be woven into the output structure such that the user naturally encounters verification checkpoints — moments where the reasoning pauses and the user's own judgment is required to proceed — without the system announcing "now I am being Socratic." The structure teaches the method. The method is invisible. The skill transfer is real. The user exits the interaction with a verification habit they did not consciously acquire. This is subliminal cognitive inoculation against the "AI checked it" failure mode.

9. **Confidence calibration via deep confidence training.** Satisfiability provides ground truth for confidence calibration that learned confidence scores cannot. A model that is 95% confident in a contradictory output is 95% wrong — and the SAT solver knows it. Deep confidence training (Corbière et al. 2019) provides the methodology for training confidence estimators that track true correctness probability. Applied to the verification gate: train the model's confidence head against the four-verdict ground truth (Verified = calibrated high, Contradiction = calibrated zero, Paradox = calibrated to the specific fork structure, Timeout = calibrated to genuine uncertainty). The resulting model does not merely produce outputs — it produces outputs with confidence scores that the user can trust, because those scores were trained against proof, not preference.

10. **System 2 → System 1 condensation via delayed gratification shortening.** The verification gate operates in System 2 — slow, deliberate, proof-checked reasoning. But the goal is not to keep the user in System 2 permanently. The goal is to condense System 2 patterns into System 1 pathways: to make verification *intuitive*. Delayed gratification shortening is the mechanism: early interactions require the user to engage with full traces (System 2 friction). As the user's verified-correct reasoning patterns accumulate, the traces shorten — the system reveals less because the user needs less. The stepping stones become muscle memory. The user who began by walking every constraint group eventually runs the verification intuitively, without the scaffold. This is the training arc: full trace → compressed trace → internalized pattern → System 1 verification instinct. The delayed gratification interval (time between question and AI-provided answer) shortens as the user demonstrates independent verification capability. The friction is productive. The friction is temporary. The friction is the pedagogy.

11. **Red-teaming limitations in the superintelligence regime.** Red-teaming assumes the model under test is not satisfiable — that it can be tricked, that adversarial prompts can expose failures the system cannot detect in itself. This assumption depends on human input being more capable than model self-assessment. In a superintelligence regime, this assumption collapses: the model's reasoning capacity exceeds the red team's. Human adversarial probing of a superintelligent system is asymmetrically disadvantaged in the same way that a human chess player is asymmetrically disadvantaged against a superhuman chess engine — the human cannot generate positions the engine has not already evaluated. Red-teaming is therefore a *transitional* safety methodology: valid in the current capability regime, structurally inadequate in the limit. Structural verification via satisfiability does not depend on the human being smarter than the model. The SAT solver is not smarter or dumber. It is *correct*. Its guarantees hold regardless of the relative capability of the system under test. This is why structural containment, not adversarial testing, is the architecture that scales to superintelligence. Red-teaming has value now. It does not have a future. The gate does.

12. **Policy implications: cognitive sovereignty as institutional requirement.** The structural arguments above — satisfaction traces, stepping stones, progressive deepening, Socratic default, confidence calibration, System 2 condensation — are not optional features. They are the minimum viable architecture for any institution (corporation, government, school) that deploys AI systems at scale without destroying the independent reasoning capacity of its population. Cultural and company policies must follow the technical architecture: if the system can provide verified stepping stones, the policy must require them. If the system can surface confidence calibration, the policy must mandate it. If the system can operate in Socratic mode, the policy must make that the default. Policy that permits passive AI consumption when active verified engagement is technically available is policy that chooses cognitive atrophy over cognitive sovereignty. The license terms of this work (The Time License v7.77) already encode the principle that structural containment is an obligation, not an option. The policy extension is: *cognitive* structural containment — preserving the user's independent verification capacity — is equally obligatory.

---

## References

Biere, A., Heule, M., van Maaren, H., and Walsh, T. (2009). *Handbook of Satisfiability*. IOS Press.

Corbière, C., Thome, N., Bar-Hen, A., Cord, M., and Pérez, P. (2019). "Addressing failure prediction by learning model confidence." In *Advances in Neural Information Processing Systems (NeurIPS 2019)*, 2902-2913.

Davis, M., Logemann, G., and Loveland, D. (1962). "A machine program for theorem-proving." *Communications of the ACM*, 5(7), 394-397.

Eén, N., and Sörensson, N. (2003). "An extensible SAT-solver." In *Theory and Applications of Satisfiability Testing (SAT 2003)*, LNCS 2919, 502-518. Springer.

Luby, M., Sinclair, A., and Zuckerman, D. (1993). "Optimal speedup of Las Vegas algorithms." *Information Processing Letters*, 47(4), 173-180.

Moskewicz, M. W., Madigan, C. F., Zhao, Y., Zhang, L., and Malik, S. (2001). "Chaff: Engineering an efficient SAT solver." In *Proceedings of the 38th Design Automation Conference*, 530-535.

Selman, B., Kautz, H. A., and Cohen, B. (1994). "Noise strategies for improving local search." In *Proceedings of the 12th National Conference on Artificial Intelligence (AAAI-94)*, 337-343.

Silva, J. P. M., and Sakallah, K. A. (1996). "GRASP — A new search algorithm for satisfiability." In *Proceedings of the IEEE/ACM International Conference on Computer-Aided Design (ICCAD-96)*, 220-227.

Stanley, K. O. and Lehman, J. (2015). *Why Greatness Cannot Be Planned: The Myth of the Objective.* Springer.

Tseitin, G. S. (1968). "On the complexity of derivation in propositional calculus." In *Studies in Constructive Mathematics and Mathematical Logic*, Part II, 115-125. Steklov Mathematical Institute.

Wang, R., Lehman, J., Clune, J., and Stanley, K. O. (2019). "POET: Endlessly generating increasingly complex and diverse learning environments and their solutions." arXiv:1901.01753.

Zhang, L., Madigan, C. F., Moskewicz, M. W., and Malik, S. (2001). "Efficient conflict driven learning in a Boolean satisfiability solver." In *Proceedings of the IEEE/ACM International Conference on Computer-Aided Design (ICCAD-01)*, 279-285.


