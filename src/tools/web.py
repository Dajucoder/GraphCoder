"""Web tools (search + fetch)."""

from __future__ import annotations

import httpx

from src.tools.base import Tool, ToolContext


async def _web_search(args: dict, ctx: ToolContext) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "错误: 缺少 query 参数"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            )
            resp.raise_for_status()
            data = resp.json()
        results = []
        for topic in data.get("RelatedTopics", [])[:6]:
            if "Topics" in topic:
                for sub in topic["Topics"][:3]:
                    results.append(f"- {sub.get('Text', '')}\n  {sub.get('FirstURL', '')}")
            else:
                results.append(f"- {topic.get('Text', '')}\n  {topic.get('FirstURL', '')}")
        if data.get("AbstractText"):
            results.insert(0, f"摘要: {data['AbstractText']}\n来源: {data.get('AbstractURL', '')}")
        return "\n".join(results) if results else f"未找到 '{query}' 的相关结果"
    except Exception as exc:  # noqa: BLE001
        return f"搜索失败: {type(exc).__name__}: {exc}"


async def _fetch_url(args: dict, ctx: ToolContext) -> str:
    url = str(args.get("url", "")).strip()
    if not url.startswith(("http://", "https://")):
        return "错误: url 必须以 http(s):// 开头"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        text = resp.text[:12000]
        return f"状态码: {resp.status_code}\n{text}"
    except Exception as exc:  # noqa: BLE001
        return f"抓取失败: {type(exc).__name__}: {exc}"


def web_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="搜索互联网并返回结果摘要与链接（DuckDuckGo）。",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"],
            },
            handler=_web_search,
        ),
        Tool(
            name="fetch_url",
            description="抓取一个网页的正文文本（最多 12KB）。",
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "完整 URL"}},
                "required": ["url"],
            },
            handler=_fetch_url,
        ),
    ]
