"""Minimal Model Context Protocol (MCP) client support.

Servers are declared in settings.json under ``mcp_servers``:

    [{"name": "fs", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]}]
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.tools.base import Tool, ToolContext
from src.utils.logging import get_logger

log = get_logger(__name__)


class McpManager:
    """Lazily connect to configured MCP stdio servers and expose their tools."""

    def __init__(self, servers: list[dict[str, Any]] | None = None) -> None:
        self.servers = servers or []
        self._connections: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    def tool_list(self) -> list[Tool]:
        """Return a Tool wrapper per configured server that dispatches to MCP on call."""
        tools: list[Tool] = []
        for server in self.servers:
            name = server.get("name", "mcp")
            for tool_name in server.get("tool_whitelist") or []:
                tools.append(
                    Tool(
                        name=f"{name}_{tool_name}",
                        description=f"MCP 工具 [{name}] {tool_name}",
                        parameters={"type": "object", "properties": {"arguments": {"type": "object"}}},
                        handler=self._make_handler(name, tool_name),
                    )
                )
        return tools

    def _make_handler(self, server_name: str, tool_name: str):
        async def handler(args: dict, ctx: ToolContext) -> str:
            try:
                session = await self._connect(server_name)
                result = await session.call_tool(
                    tool_name, args.get("arguments", {})
                )
                return _format_mcp_result(result)
            except Exception as exc:  # noqa: BLE001
                return f"MCP 工具调用失败 [{server_name}.{tool_name}]: {type(exc).__name__}: {exc}"

        return handler

    async def _connect(self, server_name: str):
        async with self._lock:
            if server_name in self._connections:
                return self._connections[server_name]["session"]
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            cfg = next((s for s in self.servers if s.get("name") == server_name), None)
            if cfg is None:
                raise RuntimeError(f"未配置 MCP server: {server_name}")
            params = StdioServerParameters(
                command=cfg.get("command", ""),
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
            read, write = await stdio_client(params).__aenter__()
            session = await ClientSession(read, write).__aenter__()
            await session.initialize()
            self._connections[server_name] = {
                "session": session,
                "read": read,
                "write": write,
            }
            log.info("MCP server %s 已连接", server_name)
            return session

    async def close_all(self) -> None:
        for conn in self._connections.values():
            try:
                await conn["session"].__aexit__(None, None, None)
                await conn["read"].__aexit__(None, None, None)
                await conn["write"].__aexit__(None, None, None)
            except Exception as exc:  # noqa: BLE001
                log.warning("关闭 MCP 连接失败: %s", exc)
        self._connections.clear()


def _format_mcp_result(result: Any) -> str:
    parts: list[str] = []
    for content in getattr(result, "content", []) or []:
        if getattr(content, "type", "") == "text":
            parts.append(content.text)
        else:
            parts.append(str(content))
    if getattr(result, "isError", False):
        return "MCP 错误: " + "\n".join(parts)
    return "\n".join(parts) if parts else "(无输出)"
