"""
Tests for satisfaction_suffices.logic.proof_evo — evolutionary proof search.

Covers: ProofNode, ProofStatus, MutationOp, mutation operators (all 12),
MutationBandit (UCB-1), SolverConfig, portfolio_solve, ProofEvolver,
extract_unsat_core, evolve_proof, portfolio_evolve_proof.
"""

from __future__ import annotations

import random
from typing import List

import pytest

from satisfaction_suffices.logic.proof_evo import (
    DEFAULT_PORTFOLIO,
    EvolutionResult,
    MutationBandit,
    MutationOp,
    ProofEvolver,
    ProofNode,
    ProofStatus,
    SolverConfig,
    by_analogy,
    case_split,
    contrapositive,
    decompose,
    evolve_proof,
    extract_unsat_core,
    generalize,
    induction,
    inject_lemma,
    negate_normalize,
    portfolio_evolve_proof,
    portfolio_solve,
    resolve_statements,
    specialize,
    strengthen,
)


# ═══════════════════════════════════════════════════════════════════
# ProofNode / ProofStatus
# ═══════════════════════════════════════════════════════════════════

class TestProofNode:
    def test_proved_is_resolved(self) -> None:
        node = ProofNode(id="pf_1", statement="A", status=ProofStatus.PROVED)
        assert node.is_resolved is True

    def test_refuted_is_resolved(self) -> None:
        node = ProofNode(id="pf_2", statement="A", status=ProofStatus.REFUTED)
        assert node.is_resolved is True

    def test_unresolved_is_not_resolved(self) -> None:
        node = ProofNode(id="pf_3", statement="A", status=ProofStatus.UNRESOLVED)
        assert node.is_resolved is False

    def test_evolving_is_not_resolved(self) -> None:
        node = ProofNode(id="pf_4", statement="A", status=ProofStatus.EVOLVING)
        assert node.is_resolved is False

    def test_default_fields(self) -> None:
        node = ProofNode(id="pf_5", statement="X", status=ProofStatus.UNRESOLVED)
        assert node.verification is None
        assert node.parent_id is None
        assert node.children == []
        assert node.generation == 0
        assert node.fitness == 0.0
        assert node.mutations == []


# ═══════════════════════════════════════════════════════════════════
# Mutation Operators (standalone functions)
# ═══════════════════════════════════════════════════════════════════

class TestDecompose:
    def test_and_split(self) -> None:
        parts = decompose("A and B")
        assert len(parts) >= 2
        assert "a" in parts
        assert "b" in parts

    def test_implies_split(self) -> None:
        parts = decompose("A implies B")
        assert len(parts) >= 2

    def test_if_then_split(self) -> None:
        parts = decompose("if P then Q")
        assert len(parts) >= 2

    def test_sentence_split(self) -> None:
        parts = decompose("First claim. Second claim.")
        assert len(parts) >= 2

    def test_atomic_no_split(self) -> None:
        parts = decompose("hello")
        assert parts == ["hello"]


class TestContrapositive:
    def test_if_then(self) -> None:
        cp = contrapositive("if A then B")
        assert "not" in cp.lower()
        assert "b" in cp.lower() or "B" in cp

    def test_non_conditional(self) -> None:
        cp = contrapositive("X is true")
        assert "not" in cp.lower()


class TestCaseSplit:
    def test_default_cases(self) -> None:
        cases = case_split("some statement")
        assert len(cases) == 2
        assert any("positive" in c.lower() for c in cases)
        assert any("negative" in c.lower() for c in cases)

    def test_custom_cases(self) -> None:
        cases = case_split("P(n)", cases=["n=0", "n>0"])
        assert len(cases) == 2
        assert "n=0" in cases[0]


class TestStrengthen:
    def test_basic(self) -> None:
        result = strengthen("conclusion", "premise")
        assert "premise" in result
        assert "conclusion" in result


class TestInjectLemma:
    def test_basic(self) -> None:
        result = inject_lemma("goal", "helper lemma")
        assert "helper lemma" in result
        assert "goal" in result


class TestInduction:
    def test_universal(self) -> None:
        parts = induction("for all n, P(n)")
        assert len(parts) == 2
        assert any("base" in p.lower() for p in parts)
        assert any("inductive" in p.lower() or "step" in p.lower() for p in parts)

    def test_no_quantifier(self) -> None:
        parts = induction("some property holds")
        assert len(parts) == 2


class TestGeneralize:
    def test_number_generalization(self) -> None:
        result = generalize("f(42) > 0")
        assert "for all" in result.lower()
        assert "N" in result

    def test_name_generalization(self) -> None:
        result = generalize("Alice knows Bob")
        assert "for all" in result.lower() or "For all" in result

    def test_no_specifics(self) -> None:
        result = generalize("x > y")
        assert "for all" in result.lower()


class TestSpecialize:
    def test_with_quantifier(self) -> None:
        result = specialize("for all n, P(n)", "5")
        assert "5" in result

    def test_without_quantifier(self) -> None:
        result = specialize("some expression", "0")
        assert "0" in result


class TestNegateNormalize:
    def test_double_negation(self) -> None:
        result = negate_normalize("not not A")
        assert "not not" not in result.lower()

    def test_demorgan_and(self) -> None:
        result = negate_normalize("not (X and Y)")
        assert "or" in result.lower()

    def test_demorgan_or(self) -> None:
        result = negate_normalize("not (X or Y)")
        assert "and" in result.lower()

    def test_no_change(self) -> None:
        result = negate_normalize("A or B")
        assert result.strip() == "A or B"


class TestResolveStatements:
    def test_basic_resolution(self) -> None:
        result = resolve_statements("A and B", "not A and C")
        assert result is not None

    def test_no_resolution(self) -> None:
        result = resolve_statements("A and B", "C and D")
        assert result is None


class TestByAnalogy:
    def test_if_then_template(self) -> None:
        result = by_analogy("P and Q", "if X then Y")
        assert len(result) > 0

    def test_given_template(self) -> None:
        result = by_analogy("P and Q", "Given X. finish Y")
        assert "By analogy" in result or "Given" in result

    def test_atomic_fallback(self) -> None:
        result = by_analogy("single", "if X then Y")
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════
# MutationBandit (UCB-1)
# ═══════════════════════════════════════════════════════════════════

class TestMutationBandit:
    def test_initial_exploration(self) -> None:
        ops = [MutationOp.DECOMPOSE, MutationOp.CONTRAPOSITIVE, MutationOp.WEAKEN]
        bandit = MutationBandit(ops)
        rng = random.Random(42)
        # First N pulls should cover all arms (each arm pulled at least once)
        selected = set()
        for _ in range(len(ops) * 4):
            op = bandit.select(rng)
            selected.add(op)
            bandit.update(op, 0.1)
        assert selected == set(ops)

    def test_update_and_exploit(self) -> None:
        ops = [MutationOp.DECOMPOSE, MutationOp.CONTRAPOSITIVE]
        bandit = MutationBandit(ops, c=0.01)  # low exploration → exploit
        rng = random.Random(42)
        # Pull each once
        for op in ops:
            bandit.select(rng)
            bandit.update(op, 0.0)
        # Give DECOMPOSE high reward
        bandit.update(MutationOp.DECOMPOSE, 1.0)
        # Next selection should favor DECOMPOSE
        selections = [bandit.select(rng) for _ in range(20)]
        assert selections.count(MutationOp.DECOMPOSE) > selections.count(MutationOp.CONTRAPOSITIVE)

    def test_stats(self) -> None:
        ops = [MutationOp.DECOMPOSE, MutationOp.WEAKEN]
        bandit = MutationBandit(ops)
        rng = random.Random(0)
        op1 = bandit.select(rng)
        bandit.update(op1, 0.5)
        stats = bandit.stats()
        assert op1.name in stats
        assert stats[op1.name]["pulls"] == 1
        assert stats[op1.name]["mean_reward"] == 0.5

    def test_negative_reward_clamped(self) -> None:
        ops = [MutationOp.GENERALIZE]
        bandit = MutationBandit(ops)
        rng = random.Random(0)
        bandit.select(rng)
        bandit.update(MutationOp.GENERALIZE, -5.0)
        stats = bandit.stats()
        assert stats["GENERALIZE"]["mean_reward"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# SolverConfig / Portfolio Solve
# ═══════════════════════════════════════════════════════════════════

class TestSolverConfig:
    def test_default_portfolio_exists(self) -> None:
        assert len(DEFAULT_PORTFOLIO) >= 3

    def test_config_apply_noop_on_simple_solver(self) -> None:
        from satisfaction_suffices.verifier.sat import CDCLSolver
        cfg = SolverConfig("test", budget=100, var_decay=0.5, phase_init=True)
        solver = CDCLSolver()
        solver.new_vars(3)
        # apply should not raise even if solver lacks _var_decay/_polarity
        cfg.apply(solver)


class TestPortfolioSolve:
    def test_simple_sat(self) -> None:
        # x1 or x2 (1-indexed DIMACS-style)
        clauses = [[1, 2]]
        sat, model, name = portfolio_solve(2, clauses)
        assert sat is True
        assert model is not None

    def test_simple_unsat(self) -> None:
        # x and not-x
        clauses = [[1], [-1]]
        sat, model, name = portfolio_solve(1, clauses)
        assert sat is False
        assert name == "all_unsat"

    def test_custom_configs(self) -> None:
        configs = [SolverConfig("mini", budget=100)]
        clauses = [[1, 2]]
        sat, model, name = portfolio_solve(2, clauses, configs=configs)
        assert sat is True
        assert name == "mini"


# ═══════════════════════════════════════════════════════════════════
# ProofEvolver
# ═══════════════════════════════════════════════════════════════════

class TestProofEvolver:
    def test_already_verified(self) -> None:
        evolver = ProofEvolver(population_size=4, max_generations=3, seed=42)
        result = evolver.evolve("if A then B. A.")
        assert result.resolved is True
        assert result.best_node.status == ProofStatus.PROVED
        assert result.generations == 0

    def test_evolve_unresolvable(self) -> None:
        # Use logic domain statement that the proof domain won't immediately verify
        evolver = ProofEvolver(population_size=4, max_generations=2, seed=42)
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert isinstance(result, EvolutionResult)
        assert result.elapsed_ms >= 0

    def test_evolve_with_seed_lemmas(self) -> None:
        evolver = ProofEvolver(population_size=4, max_generations=3, seed=42)
        result = evolver.evolve("if P then Q", seed_lemmas=["P is true", "Q follows"])
        assert isinstance(result, EvolutionResult)
        assert len(evolver.lemma_bank) >= 2  # seed lemmas + any discovered

    def test_lemma_bank_grows(self) -> None:
        evolver = ProofEvolver(population_size=4, max_generations=3, seed=42)
        evolver.evolve("if A then B. A.")
        # A verified statement should be in the lemma bank
        assert len(evolver.lemma_bank) >= 1

    def test_evolution_tree_populated(self) -> None:
        # Use a statement that won't immediately resolve in proof domain
        evolver = ProofEvolver(population_size=4, max_generations=2, seed=42)
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert len(result.evolution_tree) >= 1

    def test_mutation_stats_populated(self) -> None:
        evolver = ProofEvolver(population_size=4, max_generations=2, seed=42)
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert result.mutation_stats is not None
        assert len(result.mutation_stats) > 0

    def test_diversity_computed(self) -> None:
        evolver = ProofEvolver(population_size=6, max_generations=2, seed=42)
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert 0.0 <= result.diversity <= 1.0

    def test_large_population(self) -> None:
        evolver = ProofEvolver(population_size=12, max_generations=2, seed=42)
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert result.total_candidates >= 1

    def test_crossover_exercises(self) -> None:
        evolver = ProofEvolver(population_size=8, max_generations=3, seed=42)
        evolver._crossover_rate = 0.9  # force crossover
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert result.total_candidates >= 1

    def test_stagnation_injection(self) -> None:
        evolver = ProofEvolver(population_size=4, max_generations=5, seed=42)
        evolver._stagnation_window = 2
        result = evolver.evolve("the sky is blue and the sky is not blue and nothing resolves")
        assert isinstance(result, EvolutionResult)


class TestEvolveProof:
    def test_convenience_simple(self) -> None:
        result = evolve_proof("if A then B. A.", max_generations=3)
        assert result.resolved is True
        assert result.best_node.status == ProofStatus.PROVED

    def test_convenience_contradiction(self) -> None:
        result = evolve_proof("A. not A.", max_generations=5, population_size=4)
        assert isinstance(result, EvolutionResult)

    def test_portfolio_evolve(self) -> None:
        result = portfolio_evolve_proof(
            "if A then B. A.",
            max_generations=3,
            population_size=4,
            n_runs=2,
        )
        assert result.resolved is True

    def test_portfolio_evolve_hard(self) -> None:
        result = portfolio_evolve_proof(
            "A. not A.",
            max_generations=3,
            population_size=4,
            n_runs=2,
        )
        assert isinstance(result, EvolutionResult)


# ═══════════════════════════════════════════════════════════════════
# UNSAT Core Extraction
# ═══════════════════════════════════════════════════════════════════

class TestExtractUnsatCore:
    def test_simple_unsat(self) -> None:
        # x and not-x → core is the whole thing
        clauses = [[1], [-1]]
        core = extract_unsat_core(1, clauses)
        assert core is not None
        assert len(core) == 2

    def test_sat_returns_none(self) -> None:
        clauses = [[1, 2], [-1, 2]]
        core = extract_unsat_core(2, clauses)
        assert core is None

    def test_redundant_clause_removed(self) -> None:
        # x, not-x, y — core is x, not-x; y is redundant
        clauses = [[1], [-1], [2]]
        core = extract_unsat_core(2, clauses)
        assert core is not None
        assert len(core) == 2

    def test_larger_unsat(self) -> None:
        # PHP(3,2): 3 pigeons, 2 holes — provably UNSAT
        from satisfaction_suffices.logic.ppl import pigeonhole_cnf
        n_vars, clauses = pigeonhole_cnf(3, 2)
        core = extract_unsat_core(n_vars, clauses)
        assert core is not None
        assert len(core) <= len(clauses)


# ═══════════════════════════════════════════════════════════════════
# EvolutionResult
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionResult:
    def test_fields(self) -> None:
        node = ProofNode(id="pf_0", statement="A", status=ProofStatus.PROVED)
        result = EvolutionResult(
            resolved=True,
            best_node=node,
            generations=5,
            total_candidates=20,
            proved_count=3,
            refuted_count=2,
            unresolved_count=15,
            elapsed_ms=42.0,
            evolution_tree={"pf_0": node},
        )
        assert result.resolved is True
        assert result.generations == 5
        assert result.diversity == 0.0  # default
