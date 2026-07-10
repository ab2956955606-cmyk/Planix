# Cognitive Planning Kernel Acceptance Map

This document maps the Phase 6 acceptance criteria to authoritative implementation and test evidence.

| # | Requirement | Implementation evidence | Automated evidence |
|---|---|---|---|
| 1 | No fixed content templates in normal cognitive planning | `cognitive_planning/agents/*`; legacy content isolated in `legacy_deep_planning.py` | forbidden-output and facade tests in `planning_evals/test_cognitive_kernel.py` |
| 2 | AI identifies decision-relevant unknowns | `contracts/goal_model.py`; `GoalModelingAgent` prompt | swimming high-value-question golden test |
| 3 | At most three questions with reasons | `UserGoalModel.questions` max length 3; Goal card renders reasons | swimming goal test and cognitive card test |
| 4 | Memory becomes planning rules, not retrieval counts | `ContextEvidenceAgent`, Memory/PlanningHistory/Hypothesis retrievers | mixed memory evidence and next-session hypothesis tests |
| 5 | Resources are candidates selected by AI | `ResourceResearch` plus `EvidencePack`; static catalog is candidate-only | web approval and cross-domain resource tests |
| 6 | Strategies explain rationale, tradeoffs, risks, assumptions | `StrategyPortfolio` contracts and card | standalone agent and card tests |
| 7 | Strategy approval precedes execution | persisted `approved_strategy_id`; `_approved_strategy` gate; approval decisions reference the approved artifact version | full flow and tampered approval tests |
| 8 | Tasks contain actions, evidence, deliverable, resources, fallback | `ExecutionBlueprint` contract and deterministic guards for blank task/resource semantics | Python/travel/fitness/exam/MVP golden tests and blank-semantics guard test |
| 9 | Independent Critic can veto and request repair | distinct `planning_critique` call; bounded repair graph | critic repair, mismatch, and inconsistent-pass tests |
| 10 | Model failure stops formal planning | `PlanningModelUnavailable`, `blocked_model_unavailable` | auth, timeout, invalid JSON, and P Mode failure tests |
| 11 | Critic failure blocks Calendar | `calendar_write_allowed` and `calendar_gate_node` | mismatch/template/tampered gate and end-to-end PermissionGate tests |
| 12 | Feedback diagnoses and repairs the responsible artifact | `feedback_learning_node` and `repair_router_node` | strategy, execution, goal/evidence/strategy repair-routing tests |
| 13 | Learned rules carry evidence, confidence, and domain scope | `user_planning_hypotheses` and repository | tentative/confirmed/conflicted/expired/domain-filter tests |
| 14 | Domains do not share content templates | generic contracts plus model-owned `domainExtensions` | swimming, Python career, Xinjiang travel, fitness, MVP, and CET-4 tests |
| 15 | P Mode replay and legacy threads remain readable | compatibility and replay event adapters | cognitive stream/replay tests plus existing command replay suite |
| 16 | Existing and golden tests pass without real model calls | stub/fake providers in `backend/tests/planning_evals` | full backend, frontend, type, lint, and build verification commands |

## Rollout Boundaries

- `PLANIX_USE_COGNITIVE_PLANNING=false` remains the default during rollout.
- All six `planning_*` routing rules normalize `localFallbackEnabled=false`; Settings exposes this as a disabled safety control rather than a misleading fallback option.
- `deep_planning.py` is the compatibility facade.
- `legacy_deep_planning.py` is frozen as `legacy-template-v1` and is never a cognitive error fallback.
- Model and human-gate decisions persist input/output artifact IDs so the approved and reviewed versions remain auditable in replay.
- `CognitivePlanningShadowRunner` is explicit QA tooling. It uses isolated shadow thread IDs and stores only safe comparison metrics in `planning_shadow_runs`.
- Dashboard Runtime and Goals are outside this migration.
