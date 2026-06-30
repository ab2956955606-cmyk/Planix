AGENT_TOOLS = [
    {
        "name": "create_task",
        "description": "Create a calendar task with a time, title and planning reason.",
        "parameters": {"time": "HH:mm", "title": "task title", "reason": "why this task exists"},
    },
    {
        "name": "search_materials",
        "description": "Retrieve relevant snippets from uploaded or pasted materials.",
        "parameters": {"query": "search query", "top_k": "number of snippets"},
    },
    {
        "name": "summarize_week",
        "description": "Summarize weekly completion records and suggest next actions.",
        "parameters": {"date": "week date", "plans": "weekly plan records"},
    },
]


def list_tools() -> list[dict[str, object]]:
    return AGENT_TOOLS
