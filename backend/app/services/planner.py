from backend.app.db import load_memory, save_event
from backend.app.schemas import AiPayload
from backend.app.services.tools import list_tools


class PlannerAgent:
    def plan(self, payload: AiPayload) -> dict[str, object]:
        preferences = payload.preferences or load_memory()
        save_event("plan", payload.model_dump_json(by_alias=True))
        goal = payload.goal or "AI application internship"
        return {
            "mode": "api",
            "summary": f"围绕「{goal}」生成阶段计划，每天投入 {payload.daily_hours:g} 小时。",
            "phases": [
                {"title": "阶段 1：岗位能力对齐", "detail": "拆解 JD 高频技能，建立学习清单和刷题节奏。"},
                {"title": "阶段 2：AI 应用项目冲刺", "detail": "完成 RAG、Agent、Memory、Eval 和部署闭环。"},
                {"title": "阶段 3：投递与复盘", "detail": "把项目讲法、简历 bullet 和面试题库联动优化。"},
            ],
            "tasks": [
                {"time": "09:00", "title": "阅读目标岗位 JD 并提取 5 个关键词", "reason": "让当天任务和真实岗位要求对齐。"},
                {"time": "14:30", "title": "实现或优化一个 AI 应用功能", "reason": "每天保留可展示的工程产出。"},
                {"time": "20:30", "title": "记录完成情况并生成明日调整", "reason": "形成动态复盘闭环。"},
            ],
            "preferencesUsed": preferences,
            "toolCalls": [
                {"name": "search_materials", "arguments": {"query": goal, "top_k": 3}},
                {"name": "create_task", "arguments": {"time": "14:30", "title": "AI feature sprint"}},
                {"name": "summarize_week", "arguments": {"date": payload.date}},
            ],
            "tools": list_tools(),
        }

    def review(self, payload: AiPayload) -> dict[str, object]:
        save_event("review", payload.model_dump_json(by_alias=True))
        day = payload.data.get(payload.date, {}) if payload.data else {}
        plans = day.get("plans", [])
        done = len([plan for plan in plans if plan.get("done")])
        return {
            "mode": "api",
            "summary": f"今天完成 {done}/{len(plans)} 项。",
            "suggestions": [
                "把未完成任务拆成更小的 30-45 分钟块。",
                "保留一个能证明进度的产出，例如 commit、截图或笔记。",
                "把复盘结果写入明天的第一项任务，减少重新启动成本。",
            ],
        }
