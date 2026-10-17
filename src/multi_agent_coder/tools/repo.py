"""
Repository Tools

Tools for cloning GitHub repositories and managing indexed codebases.
"""

import subprocess
from pathlib import Path
from typing import Any

from ..indexer.chunker import chunk_repository, collect_files
from ..indexer.embedder import Embedder, index_chunks
from ..store.vector import VectorStore

from ..common.logging_config import setup_logging

logger = setup_logging(__name__)

# Where cloned repos are stored
REPOS_DIR = Path(__file__).parent.parent / "repos"

REPO_TOOLS = [
    {
        "name": "clone_and_index",
        "description": (
            "Clone a GitHub repository and index it for semantic search. "
            "Provide either a GitHub repo like 'pallets/flask' or a local path."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "GitHub repo (owner/repo) or local path",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "list_repos",
        "description": "List all indexed repositories with their chunk counts.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def normalize_collection_name(repo: str) -> str:
    """Convert repo identifier to a valid ChromaDB collection name."""
    # ChromaDB requires: 3-63 chars, starts/ends with alphanumeric, only alphanumeric/underscore/hyphen
    name = repo.replace("/", "-").replace("\\", "-").replace(".", "-").replace(" ", "-")
    # Ensure it starts with alphanumeric
    if name and not name[0].isalnum():
        name = "r-" + name
    # Truncate to 63 chars
    return name[:63]


_normalize_collection_name = normalize_collection_name


def find_repo_path(repo: str) -> Path | None:
    """Find the local filesystem path for a repository."""
    if not repo:
        return None

    # Check direct local path
    direct_path = Path(repo).expanduser()
    if direct_path.is_dir():
        return direct_path

    # Check in REPOS_DIR directly
    repo_path = REPOS_DIR / repo
    if repo_path.is_dir():
        return repo_path

    # Check normalized name
    norm_name = normalize_collection_name(repo)
    norm_path = REPOS_DIR / norm_name
    if norm_path.is_dir():
        return norm_path

    # Check local- prefixed name
    local_path = REPOS_DIR / f"local-{norm_name}"
    if local_path.is_dir():
        return local_path

    return None


def resolve_repo_path(repo: str) -> tuple[Path, str, bool]:
    """Resolve repo to a local path. Returns (path, collection_name, needs_clone)."""
    local_path = Path(repo).expanduser()
    if local_path.is_dir():
        name = "local-" + local_path.name
        return local_path, normalize_collection_name(name), False

    # Treat as GitHub repo
    name = normalize_collection_name(repo)
    clone_dir = REPOS_DIR / name
    return clone_dir, name, not clone_dir.exists()


_resolve_repo_path = resolve_repo_path


def execute_clone_and_index(
    vector_store: VectorStore, embedder: Embedder, tool_input: dict[str, Any]
) -> str:
    """Clone a repo and index it for semantic search."""
    repo = tool_input["repo"]
    repo_path, collection_name, needs_clone = _resolve_repo_path(repo)

    # Check if already indexed
    if vector_store.collection_exists(collection_name):
        collections = vector_store.list_collections()
        for c in collections:
            if c["name"] == collection_name:
                return f"Repository '{repo}' is already indexed ({c['chunks']} chunks). Ready to search!"

    # Clone if needed
    if needs_clone:
        REPOS_DIR.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/{repo}.git"
        logger.info("Cloning %s to %s", url, repo_path)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            return f"Failed to clone '{repo}': {e.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return f"Cloning '{repo}' timed out."

    # Count files and chunk
    files = collect_files(repo_path)
    chunks = chunk_repository(repo_path, collection_name)

    if not chunks:
        return f"No indexable files found in '{repo}'."

    # Embed and store
    try:
        count = index_chunks(embedder, vector_store, collection_name, chunks)
    except Exception as e:
        logger.error("Failed to embed repository chunks: %s", e)
        err_str = str(e)
        if "API_KEY_INVALID" in err_str or "UNAUTHENTICATED" in err_str:
            return f"Embedding failed for '{repo}': Authentication error. Please check your GEMINI_API_KEY."
        return f"Embedding failed for '{repo}': {e}" 

    return (
        f"Indexed '{repo}': {len(files)} files, {count} chunks. "
        f"Ready to search! Try asking about the codebase."
    )


def execute_list_repos(vector_store: VectorStore, _tool_input: dict[str, Any]) -> str:
    """List all indexed repositories."""
    collections = vector_store.list_collections()
    if not collections:
        return "No repositories indexed yet. Use clone_and_index to add one."

    lines = ["Indexed repositories:"]
    for c in collections:
        lines.append(f"  - {c['name']}: {c['chunks']} chunks")
    return "\n".join(lines)


# -- Git Worktree Isolation Manager -----------------------------------------

def create_worktree(repo_dir: Path, ticket_id: str) -> Path:
    """
    Create an isolated git worktree for a ticket on a dedicated branch.
    Guarantees agents do not corrupt the working tree or dirty each other's files.
    """
    repo = repo_dir.resolve()
    worktree_path = repo / ".worktrees" / f"ticket-{ticket_id.lower()}"
    branch_name = f"agent/ticket-{ticket_id.lower()}"

    # Ensure parent directory exists
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Prune stale worktrees first
    prune_worktrees(repo)

    # If worktree already exists, remove it cleanly
    if worktree_path.exists():
        remove_worktree(repo, ticket_id)

    # Create worktree with dedicated branch
    cmd = ["git", "worktree", "add", "-B", branch_name, str(worktree_path)]
    subprocess.run(cmd, cwd=str(repo), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return worktree_path


def remove_worktree(repo_dir: Path, ticket_id: str) -> None:
    """Safely remove a ticket worktree and prune metadata."""
    repo = repo_dir.resolve()
    worktree_path = repo / ".worktrees" / f"ticket-{ticket_id.lower()}"

    if worktree_path.exists():
        cmd = ["git", "worktree", "remove", "--force", str(worktree_path)]
        subprocess.run(cmd, cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    prune_worktrees(repo)


def merge_worktree(repo_dir: Path, ticket_id: str, target_branch: str = "main") -> None:
    """
    Merge the ticket worktree branch into the target branch.
    Serializes changes cleanly back to main.
    """
    repo = repo_dir.resolve()
    branch_name = f"agent/ticket-{ticket_id.lower()}"

    # Commit any uncommitted changes in the worktree if present
    worktree_path = repo / ".worktrees" / f"ticket-{ticket_id.lower()}"
    if worktree_path.exists():
        subprocess.run(["git", "add", "-A"], cwd=str(worktree_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(
            ["git", "commit", "-m", f"Auto-commit ticket {ticket_id}"],
            cwd=str(worktree_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    # Merge branch into target branch in repo_dir
    subprocess.run(["git", "checkout", target_branch], cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cmd = ["git", "merge", branch_name, "-m", f"Merge ticket {ticket_id}"]
    subprocess.run(cmd, cwd=str(repo), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def prune_worktrees(repo_dir: Path) -> None:
    """Prune stale git worktrees."""
    repo = repo_dir.resolve()
    cmd = ["git", "worktree", "prune"]
    subprocess.run(cmd, cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
