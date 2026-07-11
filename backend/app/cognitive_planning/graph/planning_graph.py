from __future__ import annotations

from langgraph.graph import END, StateGraph

from ...services.cognitive_planning.contracts import CognitivePlanningState


def _from_guard(state: CognitivePlanningState) -> str:
    if state.get("user_action") == "continue_current_stage":
        resume_node = str(state.get("resume_node") or "")
        if (
            state.get("status") == "MODEL_UNAVAILABLE"
            and resume_node
            in {
                "goal_intelligence",
                "goal_completion",
                "reality",
                "evidence",
                "strategy",
                "execution",
                "critic",
                "feedback_learning",
            }
        ):
            return resume_node
        completion = state.get("goal_completion")
        if completion and not completion.complete:
            return "wait_for_goal_answer"
        if resume_node in {"reality", "evidence", "strategy", "execution", "critic", "feedback_learning"}:
            return resume_node
        return {
            "goal_clarification": "wait_for_goal_answer",
            "goal_understood": "reality",
            "evidence_pending": "evidence",
            "strategy_pending": "strategy",
            "execution_pending": "wait_for_execution_approval",
            "calendar_pending": "calendar_gate",
        }.get(str(state.get("business_status") or ""), "wait_for_goal_answer")
    return {
        "create": "goal_intelligence",
        "answer_question": "goal_intelligence",
        "approve_strategy": "execution",
        "revise_strategy": "strategy",
        "approve_execution": "wait_for_execution_approval",
        "give_feedback": "feedback_learning",
        "write_calendar": "calendar_gate",
        "restart": "goal_intelligence",
    }.get(state.get("user_action", "create"), "goal_intelligence")


def _after_goal(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    return "goal_completion" if state.get("goal_model") else "wait_for_goal_answer"


def _after_goal_completion(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    completion = state.get("goal_completion")
    return "reality" if completion and completion.complete else "wait_for_goal_answer"


def _after_reality(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    reality = state.get("reality_assessment")
    return "evidence" if reality and reality.can_proceed_to_evidence else "wait_for_goal_answer"


def _after_evidence(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    evidence = state.get("evidence_pack")
    return "strategy" if evidence and evidence.can_proceed_to_strategy else "wait_for_goal_answer"


def _after_strategy(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed" or not state.get("strategy_portfolio"):
        return "__end__"
    return "execution" if state.get("repair_loop") else "wait_for_strategy_approval"


def _after_execution(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    return "critic" if state.get("execution_blueprint") else "__end__"


def _after_critic(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    critique = state.get("critique_report")
    if not critique or critique.status in {"passed", "blocked"}:
        return "wait_for_execution_approval"
    return "repair" if int(state.get("repair_count", 0)) < 2 else "wait_for_execution_approval"


def _after_repair(state: CognitivePlanningState) -> str:
    return str(state.get("next_node") or "__end__")


def _after_feedback(state: CognitivePlanningState) -> str:
    if state.get("planning_mode") != "model_backed":
        return "__end__"
    update = state.get("learning_update")
    return "repair" if update and update.current_plan_patch else "__end__"


def build_cognitive_os_graph(runtime):
    graph = StateGraph(CognitivePlanningState)
    graph.add_node("session_guard", runtime.session_guard_node)
    graph.add_node("goal_intelligence", runtime.goal_modeling_node)
    graph.add_node("goal_completion", runtime.goal_completion_node)
    graph.add_node("reality", runtime.reality_assessment_node)
    graph.add_node("evidence", runtime.context_evidence_node)
    graph.add_node("strategy", runtime.strategy_architect_node)
    graph.add_node("execution", runtime.execution_designer_node)
    graph.add_node("critic", runtime.independent_critic_node)
    graph.add_node("repair", runtime.repair_router_node)
    graph.add_node("feedback_learning", runtime.feedback_learning_node)
    graph.add_node("calendar_gate", runtime.calendar_gate_node)
    graph.add_node("wait_for_goal_answer", runtime.wait_for_goal_answer_node)
    graph.add_node("wait_for_strategy_approval", runtime.wait_for_strategy_approval_node)
    graph.add_node("wait_for_execution_approval", runtime.wait_for_execution_approval_node)
    graph.set_entry_point("session_guard")
    graph.add_conditional_edges("session_guard", _from_guard, {
        "goal_intelligence": "goal_intelligence",
        "goal_completion": "goal_completion",
        "reality": "reality",
        "evidence": "evidence",
        "strategy": "strategy",
        "execution": "execution",
        "critic": "critic",
        "feedback_learning": "feedback_learning",
        "wait_for_goal_answer": "wait_for_goal_answer",
        "wait_for_strategy_approval": "wait_for_strategy_approval",
        "wait_for_execution_approval": "wait_for_execution_approval",
        "calendar_gate": "calendar_gate",
    })
    graph.add_conditional_edges("goal_intelligence", _after_goal, {
        "goal_completion": "goal_completion", "wait_for_goal_answer": "wait_for_goal_answer", "__end__": END,
    })
    graph.add_conditional_edges("goal_completion", _after_goal_completion, {
        "reality": "reality", "wait_for_goal_answer": "wait_for_goal_answer", "__end__": END,
    })
    graph.add_conditional_edges("reality", _after_reality, {
        "evidence": "evidence", "wait_for_goal_answer": "wait_for_goal_answer", "__end__": END,
    })
    graph.add_conditional_edges("evidence", _after_evidence, {
        "strategy": "strategy", "wait_for_goal_answer": "wait_for_goal_answer", "__end__": END,
    })
    graph.add_conditional_edges("strategy", _after_strategy, {
        "execution": "execution", "wait_for_strategy_approval": "wait_for_strategy_approval", "__end__": END,
    })
    graph.add_conditional_edges("execution", _after_execution, {"critic": "critic", "__end__": END})
    graph.add_conditional_edges("critic", _after_critic, {
        "repair": "repair", "wait_for_execution_approval": "wait_for_execution_approval", "__end__": END,
    })
    graph.add_conditional_edges("repair", _after_repair, {
        "goal_intelligence": "goal_intelligence",
        "reality": "reality",
        "evidence": "evidence",
        "strategy": "strategy",
        "execution": "execution",
        "critic": "critic",
        "__end__": END,
    })
    graph.add_conditional_edges("feedback_learning", _after_feedback, {"repair": "repair", "__end__": END})
    graph.add_edge("wait_for_goal_answer", END)
    graph.add_edge("wait_for_strategy_approval", END)
    graph.add_edge("wait_for_execution_approval", END)
    graph.add_edge("calendar_gate", END)
    return graph.compile()
