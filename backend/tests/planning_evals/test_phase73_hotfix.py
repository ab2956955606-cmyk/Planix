from __future__ import annotations

import json
from collections import Counter
from typing import Any

import pytest

from app.cognitive_planning import CognitiveOSRuntime
from app.cognitive_planning.agents import CognitiveModelClient, PlanningModelUnavailable
from app.db import get_conn
from app.schemas import CreatePlanningSessionRequest, PlanningSessionTextRequest
from app.services.cognitive_planning.contracts import (
    Constraint,
    DecisionRelevantUnknown,
    FeasibilityJudgment,
    GoalQuestion,
    GoalSuccessModel,
    KnownFact,
    SafePlanningError,
    StrategyPortfolio,
    UserGoalModel,
)

from .test_cognitive_kernel import StubCognitiveModel


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase73.db'}")
    return tmp_path


class SemanticGoProgressionModel(StubCognitiveModel):
    def __init__(self, *, fail_goal: bool = False, fail_strategy: bool = False):
        super().__init__()
        self.fail_goal = fail_goal
        self.fail_strategy = fail_strategy
        self.attempts_by_task: Counter[str] = Counter()

    def complete_contract(
        self,
        *,
        task_type: str,
        payload: dict[str, Any],
        contract_type,
        stage: str = "",
        **kwargs: Any,
    ):
        self.attempts_by_task[task_type] += 1
        if contract_type is UserGoalModel and self.fail_goal:
            raise PlanningModelUnavailable(
                stage,
                SafePlanningError(
                    stage=stage,
                    errorType="auth_error",
                    message="The goal model credentials are unavailable.",
                    retryable=False,
                    attempts=[
                        {
                            "provider": "deepseek",
                            "model": "goal-test",
                            "status": "error",
                            "errorType": "auth_error",
                            "latencyMs": 2,
                        }
                    ],
                ),
            )
        if contract_type is StrategyPortfolio and self.fail_strategy:
            raise PlanningModelUnavailable(
                stage,
                SafePlanningError(
                    stage=stage,
                    errorType="auth_error",
                    message="The strategy model credentials are unavailable.",
                    retryable=False,
                    attempts=[
                        {
                            "provider": "deepseek",
                            "model": "strategy-test",
                            "status": "error",
                            "errorType": "auth_error",
                            "latencyMs": 3,
                        }
                    ],
                ),
            )
        return super().complete_contract(
            task_type=task_type,
            payload=payload,
            contract_type=contract_type,
            stage=stage,
            **kwargs,
        )

    @staticmethod
    def _user_text(payload: dict[str, Any]) -> str:
        return "\n".join(
            str(item.get("content") or "")
            for item in payload.get("conversationHistory", [])
            if item.get("role") == "user"
        )

    def _goal(self, payload: dict[str, Any]) -> UserGoalModel:
        text = self._user_text(payload)
        lowered = text.lower()
        has_web_goal = "web开发" in lowered or "web 开发" in lowered
        has_python_background = "学过python" in lowered or "学过 python" in lowered
        has_web_background = "做过web开发" in lowered or "做过 web 开发" in lowered
        has_outcomes = "找工作" in text and "个人项目" in text
        has_weekly_time = "每周20小时" in text or "每周 20 小时" in text

        blocker: DecisionRelevantUnknown | None = None
        question: GoalQuestion
        if not has_web_goal:
            blocker = DecisionRelevantUnknown(
                key="target_use",
                description="Go 最终用于哪类开发结果",
                whyItChangesThePlan="目标用途会改变技术重点和成功标准。",
                impact="strategy",
                priority="blocking",
            )
            question = GoalQuestion(
                question="你希望 Go 最终用于哪类开发结果？",
                whyThisQuestionMatters="用途会改变技术重点和成功标准。",
                expectedDecisionImpact="strategy",
            )
        elif not has_outcomes:
            blocker = DecisionRelevantUnknown(
                key="desired_outcomes",
                description="Web 开发能力最终服务于求职、工作还是个人产出",
                whyItChangesThePlan="预期结果会改变项目深度和验收证据。",
                impact="success_criteria",
                priority="blocking",
            )
            question = GoalQuestion(
                question="你希望这项能力最终服务于什么结果？",
                whyThisQuestionMatters="预期结果会改变项目深度和验收证据。",
                expectedDecisionImpact="success criteria",
            )
        elif not has_weekly_time:
            blocker = DecisionRelevantUnknown(
                key="weekly_capacity",
                description="每周可稳定投入的时间",
                whyItChangesThePlan="可用时间决定首个项目的现实范围。",
                impact="feasibility",
                priority="blocking",
            )
            question = GoalQuestion(
                question="你每周能稳定投入多少时间？",
                whyThisQuestionMatters="可用时间决定首个项目的现实范围。",
                expectedDecisionImpact="scope and feasibility",
            )
        else:
            question = GoalQuestion(
                question="你希望何时完成第一个可展示版本？",
                whyThisQuestionMatters="期限可以优化节奏，但不会阻止当前策略设计。",
                expectedDecisionImpact="schedule refinement",
            )

        known_facts = [
            KnownFact(
                key="goal",
                statement="学习 Go 并用于 Web 开发" if has_web_goal else "学习 Go 语言",
                sourceText=text,
                confidence=1,
            )
        ]
        current_knowledge: list[str] = []
        if has_python_background:
            known_facts.append(
                KnownFact(key="python_background", statement="有 Python 经验", sourceText=text, confidence=1)
            )
            current_knowledge.append("有 Python 经验")
        if has_web_background:
            known_facts.append(
                KnownFact(key="web_background", statement="有 Web 开发经验", sourceText=text, confidence=1)
            )
            current_knowledge.append("有 Web 开发经验")
        if has_outcomes:
            known_facts.append(
                KnownFact(
                    key="purpose",
                    statement="用于找工作和个人项目",
                    sourceText=text,
                    confidence=1,
                )
            )
        if has_weekly_time:
            known_facts.append(
                KnownFact(key="weekly_time", statement="每周可投入 20 小时", sourceText=text, confidence=1)
            )

        unknowns = [blocker] if blocker else [
            DecisionRelevantUnknown(
                key="deadline",
                description="第一个可展示版本的期限",
                whyItChangesThePlan="期限只调整节奏，不改变已明确的策略方向。",
                impact="schedule",
                priority="optional",
            )
        ]
        return UserGoalModel(
            goalStatement="Go Web development" if has_web_goal else "Learn the Go language",
            desiredChange="Build employable Go Web development capability through personal projects",
            domain="go_web_development",
            possibleIntents=["找工作", "个人项目"] if has_outcomes else ["Web 开发"],
            currentKnowledge=current_knowledge,
            uncertainties=[item.description for item in unknowns],
            userLanguage=[item for item in text.splitlines() if item],
            hardConstraints=(
                [Constraint(statement="每周 20 小时", sourceText="每周20小时", category="time")]
                if has_weekly_time
                else []
            ),
            knownFacts=known_facts,
            decisionRelevantUnknowns=unknowns,
            successModel=GoalSuccessModel(
                definition="Can build and explain a reviewable Go Web service for job search and personal projects.",
                measurableSignals=["A working service passes integration checks."],
                intermediateMilestones=["The first API endpoint is reviewable."],
            ),
            feasibilityJudgment=FeasibilityJudgment(
                summary="Feasible with the stated background and weekly time budget."
            ),
            questions=[question],
            confidence=0.94 if blocker is None else 0.7,
            # Intentionally stale: the independent completion judge must own progression.
            canProceedToEvidence=False,
        )


def _full_go_request() -> str:
    return "\n".join(
        [
            "我要学go语言",
            "为了web开发",
            "学过python也做过web开发",
            "找工作和个人项目",
            "每周20小时",
        ]
    )


def _artifact_ids(session, artifact_type: str) -> list[str]:
    return [item.id for item in session.artifacts if item.artifact_type == artifact_type]


def test_phase73_multiturn_go_goal_completes_semantically_and_advances_to_strategy(isolated_db) -> None:
    model = SemanticGoProgressionModel()
    runtime = CognitiveOSRuntime(model_client=model)
    session = runtime.create_session(
        CreatePlanningSessionRequest(
            entryPoint="p_mode",
            threadId="phase73-go-progression",
            userInput="我要学go语言",
        )
    )
    assert session.goal_completion and session.goal_completion["complete"] is False

    followups = [
        "为了web开发",
        "学过python也做过web开发",
        "找工作和个人项目",
        "每周20小时",
    ]
    for index, text in enumerate(followups):
        session = runtime.clarify(session.session_id, PlanningSessionTextRequest(text=text))
        if index < len(followups) - 1:
            assert session.goal_completion and session.goal_completion["complete"] is False
            assert session.status == "needs_goal_clarification"

    assert session.status == "waiting_design_approval"
    assert session.business_status == "strategy_pending"
    assert session.runtime_status == "idle"
    assert session.goal_completion == {
        "complete": True,
        "blockingUnknowns": [],
        "optionalUnknowns": [
            "第一个可展示版本的期限",
            "你希望何时完成第一个可展示版本？",
        ],
        "nextStage": "strategy",
    }
    assert session.pending_question is None
    assert session.strategy_portfolio is not None
    assert model.attempts_by_task["planning_goal_model"] == 5

    goal_text = json.dumps(session.goal_model, ensure_ascii=False)
    assert "Go Web development" in goal_text
    assert "Python 经验" in goal_text
    assert "Web 开发经验" in goal_text
    assert "找工作和个人项目" in goal_text
    assert "每周可投入 20 小时" in goal_text
    assert session.user_input.splitlines() == ["我要学go语言", *followups]


def test_phase73_strategy_auth_failure_preserves_state_and_resumes_only_strategy(isolated_db) -> None:
    model = SemanticGoProgressionModel(fail_strategy=True)
    runtime = CognitiveOSRuntime(model_client=model)

    blocked = runtime.create_session(
        CreatePlanningSessionRequest(
            entryPoint="p_mode",
            threadId="phase73-strategy-recovery",
            userInput=_full_go_request(),
        )
    )

    assert blocked.status == "MODEL_UNAVAILABLE"
    assert blocked.business_status == "strategy_pending"
    assert blocked.runtime_status == "blocked_model"
    assert blocked.goal_completion and blocked.goal_completion["complete"] is True
    assert blocked.goal_completion["nextStage"] == "strategy"
    assert blocked.pending_question is None
    assert blocked.cognitive_metadata
    assert blocked.cognitive_metadata.planning_mode == "blocked_model_unavailable"
    assert blocked.strategy_portfolio is None
    assert blocked.execution_blueprint is None
    assert blocked.critique_report is None
    assert blocked.design_proposal is None
    assert not any(item.agent == "Strategy Agent" for item in blocked.decisions)

    stable_types = ("user_goal_model", "goal_completion", "reality_assessment", "evidence_pack")
    stable_artifacts = {kind: _artifact_ids(blocked, kind) for kind in stable_types}
    assert all(stable_artifacts.values())
    assert _artifact_ids(blocked, "strategy_portfolio") == []
    counts_before = {
        task: model.attempts_by_task[task]
        for task in ("planning_goal_model", "planning_reality", "planning_evidence")
    }
    assert model.attempts_by_task["planning_strategy"] == 1

    model.fail_strategy = False
    recovered = runtime.continue_current_stage(blocked.session_id)

    assert recovered.session_id == blocked.session_id
    assert recovered.status == "waiting_design_approval"
    assert recovered.business_status == "strategy_pending"
    assert recovered.runtime_status == "idle"
    assert recovered.cognitive_metadata
    assert recovered.cognitive_metadata.planning_mode == "model_backed"
    assert recovered.goal_completion == blocked.goal_completion
    assert recovered.strategy_portfolio is not None
    assert recovered.execution_blueprint is None
    assert model.attempts_by_task["planning_strategy"] == 2
    assert {
        task: model.attempts_by_task[task]
        for task in ("planning_goal_model", "planning_reality", "planning_evidence")
    } == counts_before
    for kind, ids in stable_artifacts.items():
        assert _artifact_ids(recovered, kind) == ids
    assert len(_artifact_ids(recovered, "strategy_portfolio")) == 1
    assert not any(
        item.agent == "Strategy Agent" and item.decision == "block"
        for item in recovered.decisions
    )


def test_phase73_goal_auth_failure_after_new_information_retries_goal_stage(isolated_db) -> None:
    model = SemanticGoProgressionModel()
    runtime = CognitiveOSRuntime(model_client=model)
    initial = runtime.create_session(
        CreatePlanningSessionRequest(
            entryPoint="p_mode",
            threadId="phase73-goal-recovery",
            userInput="Learn Go",
        )
    )
    assert initial.goal_completion and initial.goal_completion["complete"] is False
    initial_goal = initial.goal_model
    initial_completion = initial.goal_completion

    model.fail_goal = True
    blocked = runtime.clarify(
        initial.session_id,
        PlanningSessionTextRequest(text="\u4e3a\u4e86web\u5f00\u53d1"),
    )

    assert blocked.status == "MODEL_UNAVAILABLE"
    assert blocked.business_status == "goal_clarification"
    assert blocked.runtime_status == "blocked_model"
    assert blocked.goal_model == initial_goal
    assert blocked.goal_completion == initial_completion
    assert blocked.cognitive_metadata
    assert blocked.cognitive_metadata.current_stage == "goal_intelligence"
    assert model.attempts_by_task["planning_goal_model"] == 2
    assert model.attempts_by_task["planning_strategy"] == 0

    model.fail_goal = False
    recovered = runtime.continue_current_stage(blocked.session_id)

    assert recovered.status == "needs_goal_clarification"
    assert recovered.business_status == "goal_clarification"
    assert recovered.runtime_status == "idle"
    assert recovered.goal_completion and recovered.goal_completion["complete"] is False
    assert recovered.goal_completion != initial_completion
    assert recovered.goal_model and recovered.goal_model != initial_goal
    assert recovered.goal_model["goalStatement"] == "Go Web development"
    assert recovered.goal_model["decisionRelevantUnknowns"][0]["key"] == "desired_outcomes"
    assert model.attempts_by_task["planning_goal_model"] == 3
    assert model.attempts_by_task["planning_reality"] == 0
    assert model.attempts_by_task["planning_evidence"] == 0
    assert model.attempts_by_task["planning_strategy"] == 0


def test_phase73_next_step_control_does_not_become_goal_evidence(isolated_db) -> None:
    model = SemanticGoProgressionModel()
    runtime = CognitiveOSRuntime(model_client=model)
    blocked = runtime.create_session(
        CreatePlanningSessionRequest(
            entryPoint="p_mode",
            threadId="phase73-control-next",
            userInput="我要学go语言",
        )
    )
    calls_before = Counter(model.attempts_by_task)
    artifacts_before = [(item.id, item.artifact_type, item.version) for item in blocked.artifacts]
    input_before = blocked.user_input

    unchanged = runtime.clarify(
        blocked.session_id,
        PlanningSessionTextRequest(text="下一步"),
    )

    assert unchanged.session_id == blocked.session_id
    assert unchanged.status == "needs_goal_clarification"
    assert unchanged.business_status == "goal_clarification"
    assert unchanged.runtime_status == "idle"
    assert unchanged.user_input == input_before
    assert "下一步" not in unchanged.user_input
    assert Counter(model.attempts_by_task) == calls_before
    assert [(item.id, item.artifact_type, item.version) for item in unchanged.artifacts] == artifacts_before
    assert unchanged.goal_completion == blocked.goal_completion
    assert unchanged.pending_question == blocked.pending_question


def test_phase73_modify_control_does_not_become_revision_evidence(client, monkeypatch) -> None:
    model = SemanticGoProgressionModel()

    def complete_contract(_self, **kwargs):
        return model.complete_contract(**kwargs)

    monkeypatch.setenv("PLANIX_COGNITIVE_MODE", "true")
    monkeypatch.setattr(CognitiveModelClient, "complete_contract", complete_contract)
    started = client.post(
        "/api/command/chat",
        json={"message": _full_go_request(), "mode": "auto", "permission": "low"},
    )
    assert started.status_code == 200
    started_events = [json.loads(line) for line in started.text.splitlines() if line.strip()]
    thread_id = started_events[-1]["threadId"]
    status = next(item for item in started_events if item.get("type") == "planning_session_status")
    assert status["status"] == "waiting_design_approval"

    with get_conn() as conn:
        before = conn.execute(
            """
            SELECT id, user_input, conversation_history_json
            FROM planning_sessions
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()
    assert before is not None
    calls_before = Counter(model.attempts_by_task)

    modified = client.post(
        "/api/command/chat",
        json={
            "message": "修改",
            "mode": "auto",
            "threadId": thread_id,
            "permission": "low",
        },
    )

    assert modified.status_code == 200
    modified_events = [json.loads(line) for line in modified.text.splitlines() if line.strip()]
    assert not any(item.get("type") == "planning_session_started" for item in modified_events)
    modified_status = next(
        item for item in modified_events if item.get("type") == "planning_session_status"
    )
    assert modified_status["status"] == "waiting_design_approval"
    with get_conn() as conn:
        after = conn.execute(
            """
            SELECT id, user_input, conversation_history_json
            FROM planning_sessions
            WHERE id = ?
            """,
            (before["id"],),
        ).fetchone()
    assert after is not None
    assert after["user_input"] == before["user_input"]
    assert after["conversation_history_json"] == before["conversation_history_json"]
    assert Counter(model.attempts_by_task) == calls_before


def test_phase73_restart_control_reuses_saved_goal_not_control_text(client, monkeypatch) -> None:
    model = SemanticGoProgressionModel()

    def complete_contract(_self, **kwargs):
        return model.complete_contract(**kwargs)

    monkeypatch.setenv("PLANIX_COGNITIVE_MODE", "true")
    monkeypatch.setattr(CognitiveModelClient, "complete_contract", complete_contract)
    started = client.post(
        "/api/command/chat",
        json={"message": _full_go_request(), "mode": "auto", "permission": "low"},
    )
    assert started.status_code == 200
    started_events = [json.loads(line) for line in started.text.splitlines() if line.strip()]
    thread_id = started_events[-1]["threadId"]
    with get_conn() as conn:
        original = conn.execute(
            """
            SELECT id, user_input
            FROM planning_sessions
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()
    assert original is not None

    restarted = client.post(
        "/api/command/chat",
        json={
            "message": "重新开始",
            "mode": "auto",
            "threadId": thread_id,
            "permission": "low",
        },
    )

    assert restarted.status_code == 200
    restarted_events = [json.loads(line) for line in restarted.text.splitlines() if line.strip()]
    assert any(item.get("type") == "planning_session_started" for item in restarted_events)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, status, user_input
            FROM planning_sessions
            WHERE thread_id = ?
            ORDER BY created_at, rowid
            """,
            (thread_id,),
        ).fetchall()
    assert len(rows) == 2
    assert rows[0]["id"] == original["id"]
    assert rows[0]["status"] == "cancelled"
    assert rows[1]["user_input"] == original["user_input"]
    assert "重新开始" not in rows[1]["user_input"]


def test_phase73_stream_exposes_goal_completion_and_separate_statuses(client, monkeypatch) -> None:
    model = SemanticGoProgressionModel()

    def complete_contract(_self, **kwargs):
        return model.complete_contract(**kwargs)

    monkeypatch.setenv("PLANIX_COGNITIVE_MODE", "true")
    monkeypatch.setattr(CognitiveModelClient, "complete_contract", complete_contract)
    response = client.post(
        "/api/command/chat",
        json={"message": _full_go_request(), "mode": "auto", "permission": "low"},
    )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    completion = next(item for item in events if item.get("type") == "goal_completion_updated")
    assert completion["data"]["complete"] is True
    assert completion["data"]["blockingUnknowns"] == []
    assert completion["data"]["nextStage"] == "strategy"

    status = next(item for item in events if item.get("type") == "planning_session_status")
    assert status["status"] == "waiting_design_approval"
    assert status["businessStatus"] == "strategy_pending"
    assert status["runtimeStatus"] == "idle"
    assert status["goalCompletion"]["complete"] is True

    thread_id = events[-1]["threadId"]
    replay = client.get(f"/api/command/thread/{thread_id}")
    assert replay.status_code == 200
    assert "goal_completion_updated" in {
        item.get("kind") for item in replay.json()["messages"]
    }
