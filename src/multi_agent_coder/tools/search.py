"""
Search Tools

Semantic search and regex grep across indexed codebases.
"""

import re
from pathlib import Path
from typing import Any

from ..indexer.chunker import INDEXABLE_EXTENSIONS
from ..indexer.embedder import Embedder
from ..store.vector import VectorStore

from ..common.logging_config import setup_logging

logger = setup_logging(__name__)

# Where cloned repos are stored
REPOS_DIR = Path(__file__).parent.parent / "repos"

SEARCH_TOOLS = [
    {
        "name": "search_code",
        "description": (
            "Semantic search across indexed codebases. Use for conceptual questions "
            "like 'how does routing work?' or 'where is auth handled?'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "repo": {
                    "type": "string",
                    "description": "Limit search to specific repo (optional)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "grep",
        "description": (
            "Exact regex pattern search across repository files. "
            "Use for finding specific identifiers, TODOs, or exact strings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "repo": {
                    "type": "string",
                    "description": "Limit search to specific repo (optional)",
                },
            },
            "required": ["pattern"],
        },
    },
]


from .repo import find_repo_path, normalize_collection_name


def execute_search_code(
    vector_store: VectorStore | None,
    embedder: Embedder | None,
    tool_input: dict[str, Any],
    workspace_root: Path | str | None = None,
) -> str:
    """Semantic search across indexed codebases with resilient fallback to grep."""
    query = tool_input.get("query", "")
    repo = tool_input.get("repo")
    if not query:
        return "Error: 'query' parameter is required for search_code."

    if vector_store is None or embedder is None:
        logger.info("Semantic vector store / embedder unavailable; falling back to grep for query: '%s'", query)
        return execute_grep(
            vector_store=vector_store,
            _embedder=embedder,
            tool_input={"pattern": re.escape(query), "repo": repo},
            workspace_root=workspace_root,
        )

    try:
        collection_name = normalize_collection_name(repo) if repo else None
        query_embedding = embedder.embed_query(query)
        results = vector_store.search(
            query_embedding=query_embedding,
            collection_name=collection_name,
            n_results=5,
        )
    except Exception as exc:
        logger.warning("Semantic search failed (%s); falling back to grep.", exc)
        return execute_grep(
            vector_store=vector_store,
            _embedder=embedder,
            tool_input={"pattern": re.escape(query), "repo": repo},
            workspace_root=workspace_root,
        )

    if not results:
        # If vector search returned 0 results, also try grep before giving up
        grep_fallback = execute_grep(
            vector_store=vector_store,
            _embedder=embedder,
            tool_input={"pattern": re.escape(query), "repo": repo},
            workspace_root=workspace_root,
        )
        if "No matches" not in grep_fallback and "No repositories" not in grep_fallback:
            return f"No semantic embedding matches. Grep matches:\n\n{grep_fallback}"
        return f"No results found for: {query}"

    parts = [f"Search results for: '{query}'\n"]
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        score = 1 - r["distance"]  # Convert distance to similarity
        parts.append(
            f"### Result {i} (relevance: {score:.2f})\n"
            f"**{meta['filepath']}** lines {meta['start_line']}-{meta['end_line']} "
            f"[{r['collection']}]\n"
            f"```\n{r['content'][:500]}\n```\n"
        )

    return "\n".join(parts)


def execute_grep(
    vector_store: VectorStore | None = None,
    _embedder: Embedder | None = None,
    tool_input: dict[str, Any] | None = None,
    workspace_root: Path | str | None = None,
) -> str:
    """Regex search across repository files."""
    if tool_input is None:
        tool_input = {}
    pattern = tool_input.get("pattern", "")
    repo = tool_input.get("repo")

    if not pattern:
        return "Error: 'pattern' parameter is required for grep."

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    # Determine which repos/directories to search
    if workspace_root:
        target_path = Path(workspace_root).resolve()
        search_dirs = [target_path] if target_path.exists() else []
    elif repo:
        target_path = find_repo_path(repo)
        search_dirs = [target_path] if target_path and target_path.exists() else []
    else:
        search_dirs = [d for d in REPOS_DIR.iterdir() if d.is_dir()] if REPOS_DIR.exists() else []

    if not search_dirs:
        return "No repositories or workspace directories available to search."

    matches: list[str] = []
    context_lines = 2

    for repo_dir in search_dirs:
        if not repo_dir.exists():
            continue
        for filepath in repo_dir.rglob("*"):
            if not filepath.is_file() or filepath.suffix not in INDEXABLE_EXTENSIONS:
                continue

            try:
                lines = filepath.read_text(encoding="utf-8", errors="ignore").split("\n")
            except Exception:
                continue

            for i, line in enumerate(lines):
                if regex.search(line):
                    rel_path = filepath.relative_to(repo_dir)
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = "\n".join(
                        f"{'>' if j == i else ' '} {j + 1:4d} | {lines[j]}"
                        for j in range(start, end)
                    )
                    matches.append(f"**{rel_path}:{i + 1}**\n```\n{context}\n```")

                    if len(matches) >= 20:
                        break
            if len(matches) >= 20:
                break
        if len(matches) >= 20:
            break

    if not matches:
        return f"No matches for pattern: {pattern}"

    header = f"Found {len(matches)} matches for `{pattern}`"
    if len(matches) >= 20:
        header += " (showing first 20)"
    return header + "\n\n" + "\n\n".join(matches)
