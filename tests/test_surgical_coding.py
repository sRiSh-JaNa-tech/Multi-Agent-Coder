import pytest
from pathlib import Path
from multi_agent_coder.tools.coding import apply_search_replace, PatchError

def test_blocks_path_traversal(tmp_path: Path):
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        apply_search_replace(
            workspace_root=tmp_path,
            relative_path="../../outside.py",
            search_block="a",
            replace_block="b",
        )

def test_rejects_syntax_error_and_preserves_original_file(tmp_path: Path):
    target = tmp_path / "calc.py"
    original_code = "def add(a, b):\n    return a + b\n"
    target.write_text(original_code, encoding="utf-8")

    # Broken replacement missing closing parenthesis and colon
    with pytest.raises(PatchError, match="SyntaxError"):
        apply_search_replace(
            workspace_root=tmp_path,
            relative_path="calc.py",
            search_block="def add(a, b):",
            replace_block="def add(a, b",
        )

    # Original file on disk must remain completely untouched
    assert target.read_text(encoding="utf-8") == original_code

def test_rejects_ambiguous_duplicate_blocks(tmp_path: Path):
    target = tmp_path / "dup.py"
    target.write_text("x = 1\ny = 2\nx = 1\n", encoding="utf-8")

    with pytest.raises(PatchError, match="Ambiguous SEARCH block"):
        apply_search_replace(
            workspace_root=tmp_path,
            relative_path="dup.py",
            search_block="x = 1",
            replace_block="x = 99",
        )
