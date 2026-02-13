# -*- coding: utf-8 -*-
"""AgentTool [OK]

[OK] Agent [OK] Agent [OK] AgentTool [OK]
"""

from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.llm_agent import Agent


# [OK] AgentTool [OK]
# key: persona_id (e.g., "french_student_male")
# value: AgentTool [OK]
AGENT_TOOLS: dict[str, AgentTool] = {}


def register_agent_tool(pid: str, agent: Agent) -> None:
    """[OK] Agent [OK] AgentTool[OK]

    Args:
        pid: Persona ID[OK] "french_student_male"[OK]
        agent: [OK] Agent [OK]

    Example:
        >>> register_agent_tool("french_student_male", my_agent)
    """
    if pid in AGENT_TOOLS:
        print(f"[WARN] AgentTool for {pid} already registered, overwriting")
    AGENT_TOOLS[pid] = AgentTool(agent=agent)
    print(f"[INFO] Registered AgentTool: {pid}")


def get_agent_tools(exclude_pid: str | None = None) -> list[AgentTool]:
    """[OK] AgentTool[OK] persona[OK]

    Args:
        exclude_pid: [OK] persona ID[OK] "french_student_male"[OK]
                    [OK] None[OK]

    Returns:
        AgentTool [OK]

    Example:
        >>> # [OK]
        >>> tools = get_agent_tools(exclude_pid="french_student_male")
        >>> # [OK]
        >>> all_tools = get_agent_tools()
    """
    if exclude_pid is None:
        return list(AGENT_TOOLS.values())
    else:
        return [tool for pid, tool in AGENT_TOOLS.items() if pid != exclude_pid]


def clear_agent_tools() -> None:
    """[OK] AgentTool [OK]

    Example:
        >>> clear_agent_tools()
    """
    AGENT_TOOLS.clear()
    print(f"[INFO] Cleared all AgentTool cache")
