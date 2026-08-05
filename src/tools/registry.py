"""Assemble the full tool list available to agents."""

from __future__ import annotations

from src.tools.base import Tool
from src.tools.files import file_tools
from src.tools.mcp_client import McpManager
from src.tools.shell import shell_tools
from src.tools.web import web_tools


def all_tools(enable_shell: bool = True, enable_web: bool = True, mcp: McpManager | None = None) -> list[Tool]:
    tools: list[Tool] = []
    tools += file_tools()
    if enable_shell:
        tools += shell_tools()
    if enable_web:
        tools += web_tools()
    if mcp is not None:
        tools += mcp.tool_list()
    return tools
