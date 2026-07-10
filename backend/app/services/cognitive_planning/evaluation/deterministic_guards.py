from __future__ import annotations

from datetime import date
from typing import Iterable

from ..contracts import ExecutionBlueprint, PlanCritiqueReport


FORBIDDEN_TEMPLATE_PHRASES = (
    "这个主题",
    "能做小项目",
    "学习并复现",
    "完成一个可检查产出",
    "确认基础与最小路径",
    "项目驱动的稳步学习计划",
)


class DeterministicGuardError(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


def template_phrase_hits(values: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for value in values:
        for phrase in FORBIDDEN_TEMPLATE_PHRASES:
            if phrase in (value or "") and phrase not in hits:
                hits.append(phrase)
    return hits


def validate_execution_invariants(blueprint: ExecutionBlueprint) -> None:
    issues: list[str] = []
    ids = [task.id for task in blueprint.tasks]
    if len(ids) != len(set(ids)):
        issues.append("task ids must be unique")
    titles = [task.title for task in blueprint.tasks]
    for phrase in template_phrase_hits(titles):
        issues.append(f"forbidden template phrase in task title: {phrase}")
    known_ids = set(ids)
    for task in blueprint.tasks:
        if not task.title.strip():
            issues.append(f"{task.id} has no title")
        if not task.purpose.strip():
            issues.append(f"{task.id} has no purpose")
        if not task.why_now.strip():
            issues.append(f"{task.id} has no sequencing rationale")
        unknown_dependencies = [item for item in task.dependencies if item not in known_ids]
        if unknown_dependencies:
            issues.append(f"{task.id} has unknown dependencies: {', '.join(unknown_dependencies)}")
        if task.scheduled_date:
            try:
                date.fromisoformat(task.scheduled_date)
            except ValueError:
                issues.append(f"{task.id} has invalid scheduledDate")
        if not task.action_steps or any(not item.strip() for item in task.action_steps):
            issues.append(f"{task.id} has no action steps")
        if not task.completion_evidence or any(not item.strip() for item in task.completion_evidence):
            issues.append(f"{task.id} has no completion evidence")
        if not task.deliverable.strip():
            issues.append(f"{task.id} has no deliverable")
        if not task.resources:
            issues.append(f"{task.id} has no resources")
        for index, resource in enumerate(task.resources, start=1):
            if not resource.title.strip():
                issues.append(f"{task.id} resource {index} has no title")
            if not resource.exact_usage.strip():
                issues.append(f"{task.id} resource {index} has no exact usage")
            if not resource.expected_contribution.strip():
                issues.append(f"{task.id} resource {index} has no expected contribution")
        if not task.fallback_action.strip():
            issues.append(f"{task.id} has no fallback action")
    if issues:
        raise DeterministicGuardError(issues)


def calendar_write_allowed(
    *,
    planning_mode: str,
    critique: PlanCritiqueReport | None,
    strategy_approved: bool,
    execution_approved: bool,
) -> bool:
    return bool(
        planning_mode == "model_backed"
        and critique
        and critique.status == "passed"
        and critique.calendar_writable
        and not any(item.severity == "blocker" for item in critique.issues)
        and not critique.repair_requests
        and strategy_approved
        and execution_approved
    )
