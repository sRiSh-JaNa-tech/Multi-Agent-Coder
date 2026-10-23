"""Expose the installed REA MCP server to swarm worker agents."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from multi_agent_coder.tools.decorator import tool
from multi_agent_coder.security.permissions import AgentCapability


def _server_parameters(workspace_root: str | Path | None) -> StdioServerParameters:
    command = os.environ.get("REA_MCP_COMMAND") or shutil.which("npx") or "npx"
    raw_args = os.environ.get("REA_MCP_ARGS")
    if raw_args:
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            raise ValueError("REA_MCP_ARGS must be a JSON array of strings") from exc
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("REA_MCP_ARGS must be a JSON array of strings")
    else:
        version = os.environ.get("REA_MCP_VERSION", "6.7.0")
        args = ["-y", f"rea-agents@{version}", "mcp"]

    return StdioServerParameters(
        command=command,
        args=args,
        cwd=str(Path(workspace_root or Path.cwd()).resolve()),
    )


async def _list_rea_tools(
    workspace_root: str | Path | None,
    query: str,
    include_schemas: bool,
    limit: int,
) -> str:
    async with stdio_client(_server_parameters(workspace_root), errlog=sys.stderr) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.list_tools()
            normalized_query = query.casefold().strip()
            matches = [
                item for item in result.tools
                if not normalized_query
                or normalized_query in item.name.casefold()
                or normalized_query in (item.description or "").casefold()
            ]
            visible = matches[: min(200, max(1, limit))]
            return json.dumps(
                {
                    "total_tools": len(result.tools),
                    "matching_tools": len(matches),
                    "has_more": len(matches) > len(visible),
                    "tools": [
                        {
                            "name": item.name,
                            "description": item.description,
                            **({"inputSchema": item.input_schema} if include_schemas else {}),
                        }
                        for item in visible
                    ],
                },
                ensure_ascii=False,
            )


async def _call_rea_tool(
    tool_name: str,
    arguments: dict[str, Any],
    workspace_root: str | Path | None,
) -> str:
    async with stdio_client(_server_parameters(workspace_root), errlog=sys.stderr) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments, read_timeout_seconds=180)

            blocks: list[str] = []
            for item in result.content:
                text = getattr(item, "text", None)
                if text is not None:
                    blocks.append(text)
                elif getattr(item, "type", None) == "image":
                    blocks.append(f"[REA returned an image: {getattr(item, 'mime_type', 'unknown type')}]")
                else:
                    dump = getattr(item, "model_dump", None)
                    blocks.append(json.dumps(dump(mode="json") if dump else str(item), ensure_ascii=False))

            if result.structured_content is not None:
                blocks.append("Structured result:\n" + json.dumps(result.structured_content, ensure_ascii=False))
            if result.is_error:
                blocks.insert(0, "REA reported an error.")
            return "\n\n".join(blocks) or "REA returned no content."


@tool(
    name="rea_list_tools",
    description=(
        "Find REA reverse-engineering MCP tools by keyword. An empty query returns a compact "
        "overview; use a focused query such as 'binary', 'APK', or 'packet' with include_schemas=true "
        "to get matching tools and their input schemas."
    ),
    required_capability=AgentCapability.READ_ONLY,
)
def rea_list_tools(
    query: str = "",
    include_schemas: bool = False,
    limit: int = 40,
    workspace_root: str | Path | None = None,
) -> str:
    """Search the live REA tool catalog and optionally include matching input schemas."""
    return asyncio.run(_list_rea_tools(workspace_root, query, include_schemas, limit))


@tool(
    name="rea_call_tool",
    description=(
        "Call a tool on the REA reverse-engineering MCP server. First call rea_list_tools, "
        "then pass the selected tool name and its arguments object. REA analyzes "
        "targets locally and returns evidence and limitations with findings."
    ),
    required_capability=AgentCapability.EXECUTE_TESTS,
)
def rea_call_tool(
    tool_name: str,
    arguments: dict[str, Any],
    workspace_root: str | Path | None = None,
) -> str:
    """Invoke one REA MCP tool with its native argument object."""
    if not tool_name:
        return "tool_name is required; call rea_list_tools to choose an operation."
    return asyncio.run(_call_rea_tool(tool_name, arguments or {}, workspace_root))
