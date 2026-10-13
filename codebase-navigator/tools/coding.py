"""
Coding Tools

Tools for creating, modifying, and patching files within repository workspaces.
Used by the Coder and Orchestrator agents.
"""

from pathlib import Path
from typing import Any

from tools.repo import find_repo_path
from common.logging_config import setup_logging

logger = setup_logging(__name__)

CODING_TOOLS = [
    {
        "name": "create_file",
        "description": "Create a new file in a repository with given content. Fails if file already exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path (e.g., 'pallets-flask')",
                },
                "filepath": {
                    "type": "string",
                    "description": "Relative path for the new file (e.g., 'src/flask/feature.py')",
                },
                "content": {
                    "type": "string",
                    "description": "Complete text content for the new file",
                },
            },
            "required": ["repo", "filepath", "content"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite the full content of a file in a repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path",
                },
                "filepath": {
                    "type": "string",
                    "description": "Relative path to the file to write or overwrite",
                },
                "content": {
                    "type": "string",
                    "description": "Complete text content to write into the file",
                },
            },
            "required": ["repo", "filepath", "content"],
        },
    },
    {
        "name": "replace_file_content",
        "description": (
            "Surgically replace a unique block of text within an existing file. "
            "Target content must match uniquely in the file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name or path",
                },
                "filepath": {
                    "type": "string",
                    "description": "Relative path to the file",
                },
                "target_content": {
                    "type": "string",
                    "description": "Exact text block to find and replace (must be unique)",
                },
                "replacement_content": {
                    "type": "string",
                    "description": "New text block to insert in place of target_content",
                },
            },
            "required": ["repo", "filepath", "target_content", "replacement_content"],
        },
    },
]


def execute_create_file(tool_input: dict[str, Any]) -> str:
    """Create a new file with parent directories."""
    repo = tool_input.get("repo", "")
    filepath = (tool_input.get("filepath") or tool_input.get("file") or tool_input.get("path") or "").lstrip("/\\")
    content = tool_input.get("content", "")
    if not repo or not filepath:
        return "Error: 'repo' and 'filepath' parameters are required."

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    target = repo_path / filepath
    if target.exists():
        return f"File already exists: {filepath}. Use write_file or replace_file_content instead."

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        logger.info("Created %s in %s (%d lines)", filepath, repo, lines)
        return f"Successfully created {filepath} ({lines} lines)."
    except Exception as e:
        logger.error("Failed to create %s: %s", filepath, e)
        return f"Error creating file {filepath}: {e}"


def execute_write_file(tool_input: dict[str, Any]) -> str:
    """Write or overwrite file contents."""
    repo = tool_input.get("repo", "")
    filepath = (tool_input.get("filepath") or tool_input.get("file") or tool_input.get("path") or "").lstrip("/\\")
    content = tool_input.get("content", "")
    if not repo or not filepath:
        return "Error: 'repo' and 'filepath' parameters are required."

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    target = repo_path / filepath
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        action = "Updated" if existed else "Created"
        logger.info("%s %s in %s (%d lines)", action, filepath, repo, lines)
        return f"Successfully {action.lower()} {filepath} ({lines} lines)."
    except Exception as e:
        logger.error("Failed to write %s: %s", filepath, e)
        return f"Error writing file {filepath}: {e}"


def execute_replace_file_content(tool_input: dict[str, Any]) -> str:
    """Perform surgical text replacement."""
    repo = tool_input.get("repo", "")
    filepath = (tool_input.get("filepath") or tool_input.get("file") or tool_input.get("path") or "").lstrip("/\\")
    target_content = tool_input.get("target_content", "")
    replacement_content = tool_input.get("replacement_content", "")
    if not repo or not filepath:
        return "Error: 'repo' and 'filepath' parameters are required."

    repo_path = find_repo_path(repo)
    if not repo_path:
        return f"Repository '{repo}' not found."

    target = repo_path / filepath
    if not target.is_file():
        return f"File not found: {filepath} in {repo}"

    try:
        original = target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading {filepath}: {e}"

    occurrences = original.count(target_content)
    if occurrences == 0:
        return (
            f"Target content not found in {filepath}. "
            "Ensure indentation, spaces, and line breaks match exactly."
        )
    if occurrences > 1:
        return (
            f"Target content appears {occurrences} times in {filepath}. "
            "Please include more surrounding context lines to make the target block unique."
        )

    updated = original.replace(target_content, replacement_content, 1)
    try:
        target.write_text(updated, encoding="utf-8")
        logger.info("Replaced unique block in %s in %s", filepath, repo)
        return f"Successfully updated {filepath}."
    except Exception as e:
        logger.error("Failed to save changes to %s: %s", filepath, e)
        return f"Error updating file {filepath}: {e}"
