from backend.app.schemas import AiPayload


CRITERIA = [
    "actionable",
    "time-aware",
    "context-grounded",
    "adaptive",
    "reviewable",
]


class PlannerEvaluator:
    def run(self, payload: AiPayload) -> dict[str, object]:
        has_goal = bool(payload.goal.strip())
        has_context = bool(payload.materials.strip())
        has_memory = bool(payload.preferences.strip())
        has_history = bool(payload.data)
        score = 3.4 + (0.45 if has_goal else 0) + (0.35 if has_context else 0) + (0.25 if has_memory else 0) + (0.25 if has_history else 0)
        return {
            "mode": "api",
            "score": round(min(score, 5), 1),
            "criteria": CRITERIA,
            "results": [
                {"case": "clear long-term goal", "score": 5 if has_goal else 3, "reason": "goal is used as the planning anchor"},
                {"case": "materials or JD available", "score": 5 if has_context else 3, "reason": "context improves retrieval-grounded planning"},
                {"case": "preference memory available", "score": 5 if has_memory else 3, "reason": "memory personalizes schedule rhythm"},
                {"case": "historical completion records", "score": 5 if has_history else 3, "reason": "history enables dynamic review and adjustment"},
            ],
        }
