# -*- coding: utf-8 -*-
"""AgentTool 缓存和管理模块。

用于在多 Agent 协作场景中管理所有 Agent 的 AgentTool 实例。
"""

from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.llm_agent import Agent


# 全局 AgentTool 缓存
# key: persona_id (e.g., "french_student_male")
# value: AgentTool 实例
AGENT_TOOLS: dict[str, AgentTool] = {}


def register_agent_tool(pid: str, agent: Agent) -> None:
    """注册一个 Agent 为 AgentTool。

    Args:
        pid: Persona ID（如 "french_student_male"）
        agent: 要包装的 Agent 实例

    Example:
        >>> register_agent_tool("french_student_male", my_agent)
    """
    if pid in AGENT_TOOLS:
        print(f"[WARN] AgentTool for {pid} already registered, overwriting")
    AGENT_TOOLS[pid] = AgentTool(agent=agent)
    print(f"[INFO] Registered AgentTool: {pid}")


def get_agent_tools(exclude_pid: str | None = None) -> list[AgentTool]:
    """获取所有 AgentTool，可选排除指定 persona。

    Args:
        exclude_pid: 要排除的 persona ID（如 "french_student_male"）
                    如果为 None，返回所有工具

    Returns:
        AgentTool 列表

    Example:
        >>> # 获取除了法国男学生外的所有工具
        >>> tools = get_agent_tools(exclude_pid="french_student_male")
        >>> # 获取所有工具
        >>> all_tools = get_agent_tools()
    """
    if exclude_pid is None:
        return list(AGENT_TOOLS.values())
    else:
        return [tool for pid, tool in AGENT_TOOLS.items() if pid != exclude_pid]


def clear_agent_tools() -> None:
    """清空所有 AgentTool 缓存（用于测试或重置）。

    Example:
        >>> clear_agent_tools()
    """
    AGENT_TOOLS.clear()
    print(f"[INFO] Cleared all AgentTool cache")
