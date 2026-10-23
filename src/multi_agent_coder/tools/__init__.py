"""
Tool Registry for Multi-Agent Codebase Navigator & Coding Agent.
"""

from .files import FILE_TOOLS, execute_find_files, execute_list_directory, execute_read_file
from .memory import MEMORY_TOOLS, execute_recall_memory, execute_save_memory
from .repo import REPO_TOOLS, execute_clone_and_index, execute_list_repos, find_repo_path, normalize_collection_name
from .search import SEARCH_TOOLS, execute_grep, execute_search_code
from .coding import CODING_TOOLS, execute_create_file, execute_replace_file_content, execute_write_file, execute_append_file
from .execution import (
    EXECUTION_TOOLS,
    GIT_TOOLS,
    execute_check_syntax,
    execute_git_diff,
    execute_git_status,
    execute_run_command,
    execute_git_pull,
    execute_git_push,
    execute_git_commit,
    execute_git_add,
    execute_git_branch,
    execute_git_log,
)
from .outline import OUTLINE_TOOLS, execute_get_file_outline
from .registry import ToolRegistry, ToolDefinition, get_default_registry, load_custom_tools
from .decorator import tool, generate_tool_schema

__all__ = [
    # Extensible tooling
    "tool",
    "generate_tool_schema",
    "ToolRegistry",
    "ToolDefinition",
    "get_default_registry",
    "load_custom_tools",
    # Tool definitions
    "FILE_TOOLS",
    "MEMORY_TOOLS",
    "REPO_TOOLS",
    "SEARCH_TOOLS",
    "CODING_TOOLS",
    "EXECUTION_TOOLS",
    "OUTLINE_TOOLS",
    # Tool executors
    "execute_read_file",
    "execute_list_directory",
    "execute_find_files",
    "execute_save_memory",
    "execute_recall_memory",
    "execute_clone_and_index",
    "execute_list_repos",
    "execute_search_code",
    "execute_grep",
    "execute_create_file",
    "execute_write_file",
    "execute_replace_file_content",
    "execute_run_command",
    "execute_git_diff",
    "execute_git_status",
    "execute_git_log",
    "execute_git_branch",
    "execute_git_add",
    "execute_git_commit",
    "execute_git_push",
    "execute_git_pull",
    "GIT_TOOLS",
    "execute_check_syntax",
    "execute_get_file_outline",
    "find_repo_path",
    "normalize_collection_name",
]
