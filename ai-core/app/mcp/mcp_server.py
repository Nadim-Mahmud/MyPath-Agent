from app.mcp.tools import get_route, report_obstacle, get_obstacles

_TOOLS = {
    "get_route":        get_route,
    "report_obstacle":  report_obstacle,
    "get_obstacles":    get_obstacles,
}

TOOL_DECLARATIONS = [t.DECLARATION for t in _TOOLS.values()]


def execute_tool(name: str, args: dict) -> dict:
    tool = _TOOLS.get(name)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    return tool.execute(args)
