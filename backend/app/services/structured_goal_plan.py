from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

from ..schemas import GoalMilestone, GoalPlanTask, PhaseItem, PlannerTask, RagSource, ReviewPlan, StructuredGoalPlan


def is_python_goal(text: str) -> bool:
    normalized = text.lower()
    return "python" in normalized or ("py" in normalized and "学习" in text)


def build_local_structured_plan(
    goal: str,
    *,
    date: str = "",
    deadline: str = "",
    daily_hours: float = 2,
    source_count: int = 0,
) -> StructuredGoalPlan:
    cleaned_goal = goal.strip() or "提升 AI 应用开发能力"
    duration_days = _duration_days(date, deadline, 28 if is_python_goal(cleaned_goal) else 21)
    start_date = _parse_date_or_none(date)

    if is_python_goal(cleaned_goal):
        title = "Python 入门到项目实战"
        description = f"用 {duration_days} 天掌握 Python 基础，完成一个可展示的小项目，并形成复盘材料。"
        milestones = [
            GoalMilestone(
                title="阶段 1：语法基础",
                description="建立 Python 基础语法和常用数据结构的手感。",
                tasks=[
                    _task("变量、数据类型与条件判断", "掌握变量、数字、字符串、布尔值和 if/else 分支。", 60, _due(start_date, 1), "high"),
                    _task("循环、函数、列表和字典", "用小练习掌握 for/while、函数拆分、list/dict 的常见操作。", 90, _due(start_date, 3), "high"),
                ],
            ),
            GoalMilestone(
                title="阶段 2：文件、模块与异常",
                description="补齐写脚本和后端项目会直接用到的基础能力。",
                tasks=[
                    _task("文件读写与路径处理", "练习读取文本、写入结果、处理相对路径和简单 CSV/JSON。", 75, _due(start_date, 6), "medium"),
                    _task("模块、包、异常和虚拟环境", "理解 import、venv、pip、try/except，为后续 FastAPI 做准备。", 90, _due(start_date, 9), "medium"),
                ],
            ),
            GoalMilestone(
                title="阶段 3：项目实战",
                description="把语法能力转成一个可以讲清楚的作品。",
                tasks=[
                    _task("命令行 Todo 小项目", "实现新增、查看、完成、删除任务，并把数据保存到本地文件。", 120, _due(start_date, 14), "high"),
                    _task("扩展一个 FastAPI 小接口", "把 Todo 或学习记录包装成简单 API，练习请求、响应和数据校验。", 120, _due(start_date, 20), "high"),
                ],
            ),
            GoalMilestone(
                title="阶段 4：复盘与作品集整理",
                description="把学习过程沉淀成面试能讲的项目证据。",
                tasks=[
                    _task("整理 README 和项目截图", "说明项目目标、技术栈、核心接口、运行方式和后续改进。", 75, _due(start_date, 24), "medium"),
                    _task("复盘薄弱点并规划下一阶段", "记录错误、高频卡点和下一阶段要补的能力。", 45, _due(start_date, min(duration_days, 28)), "medium"),
                ],
            ),
        ]
    else:
        title = cleaned_goal[:42]
        description = f"围绕“{cleaned_goal}”生成 {duration_days} 天的结构化执行计划，每天约 {daily_hours:g} 小时。"
        milestones = [
            GoalMilestone(
                title="阶段 1：目标对齐",
                description="明确目标、资料来源、当前基础和可衡量产出。",
                tasks=[
                    _task("梳理目标和截止时间", "写清楚目标验收标准、每天可用时间和当前短板。", 45, _due(start_date, 1), "high"),
                    _task("整理参考资料和约束", "把 JD、课程笔记、项目材料或历史复盘放入资料库。", 45, _due(start_date, 2), "medium"),
                ],
            ),
            GoalMilestone(
                title="阶段 2：集中产出",
                description="把目标拆成可验证的任务，并保持每日可展示进展。",
                tasks=[
                    _task("完成一个核心任务产出", "用代码、笔记、截图或清单证明当天确实推进。", 90, _due(start_date, 5), "high"),
                    _task("根据反馈调整任务顺序", "复查资料命中、今日计划和偏好，降低任务过载。", 45, _due(start_date, 8), "medium"),
                ],
            ),
            GoalMilestone(
                title="阶段 3：复盘强化",
                description="把结果沉淀成下一轮规划和展示材料。",
                tasks=[
                    _task("总结关键证据和薄弱点", "整理完成情况、卡点、引用来源和下一步动作。", 60, _due(start_date, 12), "medium"),
                    _task("生成下一阶段计划", "用复盘结论更新目标、任务和日程安排。", 45, _due(start_date, duration_days), "medium"),
                ],
            ),
        ]

    if source_count:
        description = f"{description} 本次规划参考了 {source_count} 条资料片段。"

    return StructuredGoalPlan(
        goalTitle=title,
        goalDescription=description,
        durationDays=duration_days,
        milestones=milestones,
        reviewPlan=ReviewPlan(
            frequency="daily",
            questions=[
                "今天完成了哪些可验证产出？",
                "哪些任务卡住了，原因是什么？",
                "明天最应该优先推进哪一步？",
            ],
        ),
    )


def normalize_structured_plan(raw: object, fallback: StructuredGoalPlan) -> StructuredGoalPlan:
    if not isinstance(raw, dict):
        return fallback

    milestones = _normalize_milestones(raw.get("milestones"), fallback.milestones)
    review_plan = _normalize_review_plan(raw.get("reviewPlan") or raw.get("review_plan"), fallback.review_plan)
    candidate = {
        "goalTitle": _text(raw.get("goalTitle") or raw.get("goal_title"), fallback.goal_title),
        "goalDescription": _text(raw.get("goalDescription") or raw.get("goal_description"), fallback.goal_description),
        "durationDays": _int(raw.get("durationDays") or raw.get("duration_days"), fallback.duration_days, 1, 3650),
        "milestones": [milestone.model_dump(by_alias=True) for milestone in milestones],
        "reviewPlan": review_plan.model_dump(by_alias=True),
    }
    try:
        return StructuredGoalPlan.model_validate(candidate)
    except ValidationError:
        return fallback


def derive_phase_items(plan: StructuredGoalPlan) -> list[PhaseItem]:
    return [PhaseItem(title=milestone.title, detail=milestone.description) for milestone in plan.milestones]


def derive_planner_tasks(plan: StructuredGoalPlan) -> list[PlannerTask]:
    times = ["09:00", "14:30", "20:30"]
    tasks: list[PlannerTask] = []
    for milestone in plan.milestones:
        for task in milestone.tasks:
            tasks.append(
                PlannerTask(
                    time=times[len(tasks) % len(times)],
                    title=task.title,
                    reason=f"{milestone.title}：{task.description}",
                )
            )
            if len(tasks) >= 3:
                return tasks
    return tasks


def render_goal_plan_markdown(
    plan: StructuredGoalPlan,
    sources: list[RagSource] | list[dict[str, Any]] | None = None,
    *,
    local_template: bool = False,
    today_plan_count: int = 0,
) -> str:
    lines = []
    if local_template:
        lines.append("当前使用本地规划模板生成。")
        lines.append("")
    lines.extend(
        [
            f"## {plan.goal_title}",
            plan.goal_description,
            f"周期：{plan.duration_days} 天",
            "",
        ]
    )
    for index, milestone in enumerate(plan.milestones, start=1):
        lines.append(f"### {index}. {milestone.title}")
        if milestone.description:
            lines.append(milestone.description)
        for task in milestone.tasks:
            due = f"｜截止 {task.due_date}" if task.due_date else ""
            lines.append(
                f"- [{task.priority}] {task.title}（约 {task.estimated_minutes} 分钟{due}）：{task.description}"
            )
        lines.append("")

    if today_plan_count:
        lines.append(f"当前日程中已有 {today_plan_count} 条今日任务，建议写入前先确认负载。")
        lines.append("")

    lines.append(f"复盘频率：{'每日' if plan.review_plan.frequency == 'daily' else '每周'}")
    for question in plan.review_plan.questions:
        lines.append(f"- {question}")

    source_titles = _source_titles(sources or [])
    if source_titles:
        lines.append("")
        lines.append("参考资料：")
        for index, title in enumerate(source_titles, start=1):
            lines.append(f"{index}. {title}")

    return "\n".join(lines).strip()


def _task(title: str, description: str, minutes: int, due_date: str | None, priority: str) -> GoalPlanTask:
    return GoalPlanTask(
        title=title,
        description=description,
        estimatedMinutes=minutes,
        dueDate=due_date,
        priority=priority,
    )


def _duration_days(start: str, deadline: str, fallback: int) -> int:
    start_date = _parse_date_or_none(start)
    deadline_date = _parse_date_or_none(deadline)
    if start_date and deadline_date and deadline_date > start_date:
        return max(1, min((deadline_date - start_date).days, 3650))
    return fallback


def _parse_date_or_none(value: str) -> date_type | None:
    try:
        return date_type.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _due(start: date_type | None, offset: int) -> str | None:
    if not start:
        return None
    return (start + timedelta(days=max(offset, 0))).isoformat()


def _text(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _int(value: object, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(str(value)))
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(parsed, maximum))


def _normalize_milestones(raw: object, fallback: list[GoalMilestone]) -> list[GoalMilestone]:
    if not isinstance(raw, list):
        return fallback
    milestones: list[GoalMilestone] = []
    for index, item in enumerate(raw[:6]):
        if not isinstance(item, dict):
            continue
        fallback_milestone = fallback[min(index, len(fallback) - 1)]
        tasks = _normalize_tasks(item.get("tasks"), fallback_milestone.tasks)
        if not tasks:
            tasks = fallback_milestone.tasks
        milestones.append(
            GoalMilestone(
                title=_text(item.get("title"), fallback_milestone.title),
                description=_text(item.get("description") or item.get("detail"), fallback_milestone.description),
                tasks=tasks,
            )
        )
    return milestones or fallback


def _normalize_tasks(raw: object, fallback: list[GoalPlanTask]) -> list[GoalPlanTask]:
    if not isinstance(raw, list):
        return fallback
    tasks: list[GoalPlanTask] = []
    for index, item in enumerate(raw[:10]):
        if not isinstance(item, dict):
            continue
        fallback_task = fallback[min(index, len(fallback) - 1)] if fallback else None
        priority_value = item.get("priority")
        if not priority_value and fallback_task:
            priority_value = fallback_task.priority
        priority = str(priority_value or "medium").lower()
        if priority not in {"low", "medium", "high"}:
            priority = fallback_task.priority if fallback_task else "medium"
        due_date = item.get("dueDate") or item.get("due_date")
        due_date = due_date if isinstance(due_date, str) and _parse_date_or_none(due_date) else None
        task = GoalPlanTask(
            title=_text(item.get("title"), fallback_task.title if fallback_task else "执行任务"),
            description=_text(
                item.get("description") or item.get("reason"),
                fallback_task.description if fallback_task else "推进当前目标。",
            ),
            estimatedMinutes=_int(
                item.get("estimatedMinutes") or item.get("estimated_minutes"),
                fallback_task.estimated_minutes if fallback_task else 45,
                1,
                1440,
            ),
            dueDate=due_date,
            priority=priority,
        )
        tasks.append(task)
    return tasks or fallback


def _normalize_review_plan(raw: object, fallback: ReviewPlan) -> ReviewPlan:
    if not isinstance(raw, dict):
        return fallback
    frequency = str(raw.get("frequency") or fallback.frequency).lower()
    if frequency not in {"daily", "weekly"}:
        frequency = fallback.frequency
    questions_raw = raw.get("questions")
    questions = []
    if isinstance(questions_raw, list):
        questions = [str(item).strip() for item in questions_raw[:6] if str(item).strip()]
    return ReviewPlan(frequency=frequency, questions=questions or fallback.questions)


def _source_titles(sources: list[RagSource] | list[dict[str, Any]]) -> list[str]:
    titles = []
    for source in sources:
        title = source.title if isinstance(source, RagSource) else str(source.get("title") or "")
        if title and title not in titles:
            titles.append(title)
    return titles[:5]
