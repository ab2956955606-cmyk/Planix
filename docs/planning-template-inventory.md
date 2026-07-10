# Legacy Planning Template Inventory

Phase 6.0 freezes these legacy content generators as `legacy-template-v1`.
They remain available only when the cognitive rollout flag is off and for old
replay compatibility. Cognitive planning must never call them as a model
fallback.

The frozen implementation lives in `backend/app/services/legacy_deep_planning.py`.
`backend/app/services/deep_planning.py` is only the rollout/compatibility facade.

- `_slot_contract` and domain-specific fixed clarification questions
- `_build_pending_question`
- `_build_general_execution_draft`
- `_build_python_internship_execution_draft`
- fixed design phases such as "确认基础与最小路径" and "项目驱动练习"
- generic tasks such as "学习并复现" and "完成一个可检查产出"
- direct resource assignment from `RESOURCE_CATALOG`
- deterministic semantic scoring in the legacy `DeepPlanningService`

The cognitive kernel may reuse schemas, deterministic safety invariants, and
static resources as evidence candidates. It may not reuse these content
templates to produce a formal plan.
