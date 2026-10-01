"""Reusable Coding-Agent Decision Library.

Contains typed schemas and helper constructors for common coding-agent decisions.
Built on generic Drex decision primitives.
"""
from __future__ import annotations

from typing import Any
from drex_gateway.models import ChoiceQuestion, NoulQuestion, ScoreQuestion


# 1. TASK_COMPLEXITY
def make_task_complexity_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions
        or "Classify the architectural and implementation complexity of this engineering task.",
        criteria={
            "trivial": "Self-contained single-line, config, or typo fix requiring minimal context",
            "standard": "Standard feature addition or targeted bugfix within 1-3 known files",
            "large_context": "Cross-cutting change requiring extensive repository understanding or multiple module edits",
            "architecture_heavy": "Substantial refactor, API contract change, or system redesign requiring deep reasoning",
        },
    )


# 2. TOOL_SELECTION
def make_tool_selection_question(
    available_tools: dict[str, str], instructions: str | None = None
) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions
        or "Select the single most effective tool to execute the next immediate agent action.",
        criteria=available_tools,
    )


# 3. REPOSITORY_AREA
def make_repository_area_question(
    subsystems: dict[str, str], instructions: str | None = None
) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Identify which repository subsystem or component owns this issue/state.",
        criteria=subsystems,
    )


# 4. TEST_SELECTION
def make_test_selection_question(
    test_suites: dict[str, str], instructions: str | None = None
) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions
        or "Select the most specific and relevant test suite to validate changes without running the full test suite.",
        criteria=test_suites,
    )


# 5. VERIFIER_SELECTION
def make_verifier_selection_question(
    verifiers: dict[str, str] | None = None, instructions: str | None = None
) -> ChoiceQuestion:
    crit = verifiers or {
        "unit_test": "Fast targeted unit test suite for modified modules",
        "integration_test": "Broader integration / service test suite",
        "linter_typecheck": "Static analysis, typechecker, and formatting verification",
        "full_ci_harness": "Complete multi-stage verification harness (expensive)",
        "no_verifier": "No automated verifier applicable; manual inspection only",
    }
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Choose the appropriate verification tier for validating this patch.",
        criteria=crit,
    )


# 6. FAILURE_CLASSIFICATION
def make_failure_classification_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Classify the root cause of the verification/execution failure.",
        criteria={
            "implementation_failure": "Defect or omission in product or patch code logic",
            "verifier_failure": "Outdated, incorrect, or brittle test specification/assertion",
            "toolchain_failure": "Compiler, interpreter, linter, or build tool crashed or misconfigured",
            "environment_failure": "Missing dependency, missing system package, network timeout, or socket issue",
            "upstream_failure": "Failure caused by external dependency or pre-existing baseline breakage",
            "context_stale": "Patch conflicted with branch updates or assumptions about workspace state are stale",
            "unknown": "Root cause ambiguous or insufficient diagnostic data",
        },
    )


# 7. NEXT_ACTION
def make_next_action_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Choose the optimal next action for the coding agent loop.",
        criteria={
            "retry": "Transient failure; rerun the same step immediately",
            "repair": "Direct implementation or test fix is clear; execute local repair step",
            "replan": "Current approach is flawed; generate an alternative implementation strategy",
            "escalate": "Ambiguous requirements or persistent blockage; escalate to higher-capability model or human",
            "wait_for_resource": "Process or dependency locked; wait for resource availability",
            "stop": "Task complete or unrecoverable error; terminate agent loop",
        },
    )


# 8. PATCH_RISK
def make_patch_risk_question(instructions: str | None = None) -> ScoreQuestion:
    return ScoreQuestion(
        type="score",
        instructions=instructions or "Score the blast radius and operational risk of this patch.",
        criteria=[
            "low: Minimal risk, localized changes with comprehensive tests",
            "medium: Moderate risk, touches shared helpers or API surface with adequate tests",
            "high: High risk, modifies core schemas, concurrency, migrations, or auth with high blast radius",
        ],
    )


# 9. REVIEW_READINESS
def make_review_readiness_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Determine if the generated patch is ready for review or merging.",
        criteria={
            "ready": "Patch cleanly satisfies requirements, passes tests, and is ready for final review",
            "needs_repair": "Patch has evident functional bugs, missing edge cases, or test failures needing repair",
            "needs_deep_review": "Patch is functional but touches sensitive logic requiring thorough review",
        },
    )


# 10. CI_FAILURE_ATTRIBUTION
def make_ci_failure_attribution_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Determine the attribution of this CI failure relative to the candidate patch.",
        criteria={
            "patch_caused": "Failure is directly caused by code introduced or modified by this patch",
            "baseline": "Failure existed on the base branch prior to this patch (flaky or pre-existing)",
            "infrastructure": "Failure caused by runner timeout, out of disk, or CI network glitch",
            "unknown": "Attribution cannot be determined with current logs",
        },
    )


# 11. ARCHITECTURE_ESCALATION
def make_architecture_escalation_question(instructions: str | None = None) -> NoulQuestion:
    return NoulQuestion(
        type="noul",
        instructions=instructions
        or "Does this task or failure require escalation to an expensive architecture model rather than fast local coding?",
    )


# 12. MORE_CONTEXT_REQUIRED
def make_more_context_required_question(instructions: str | None = None) -> NoulQuestion:
    return NoulQuestion(
        type="noul",
        instructions=instructions
        or "Is more repository context or file exploration necessary before proceeding with code changes?",
    )


# 13. PATCH_SCOPE_CLASS
def make_patch_scope_class_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions or "Assess the scope and diff size of this patch relative to the objective.",
        criteria={
            "too_narrow": "Patch fails to address necessary edge cases, tests, or related call sites",
            "appropriate": "Patch is focused, well-bounded, and addresses the stated problem cleanly",
            "too_broad": "Patch contains unnecessary refactoring, unrelated formatting, or excessive file churn",
        },
    )


# 14. MAINTAINER_RISK
def make_maintainer_risk_question(instructions: str | None = None) -> ChoiceQuestion:
    return ChoiceQuestion(
        type="choice",
        instructions=instructions
        or "Evaluate the risk that a maintainer will reject or demand heavy changes to this PR.",
        criteria={
            "low": "Conforms to repository conventions, clean style, high probability of smooth merge",
            "medium": "May encounter minor style or convention questions, but architecture is sound",
            "high": "High probability of maintainer pushback due to unconventional patterns or architectural mismatch",
        },
    )
