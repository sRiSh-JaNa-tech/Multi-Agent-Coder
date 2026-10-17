"""
Model Context Protocol (MCP) Server for Multi-Agent Coder.
Enables AI Clients (like Antigravity) to act as the Brain orchestrating the worker swarm.
"""

from .server import create_mcp_server, main

__all__ = ["create_mcp_server", "main"]
