"""
End-to-End Tests for Tools and Infrastructure
Tests all components across Task 1 and Phase 2.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from multi_agent_coder.common.logging_config import setup_logging
from multi_agent_coder.common.token_tracker import GeminiTokenTracker
from multi_agent_coder.store.memory import MemoryStore
from multi_agent_coder.tools.repo import find_repo_path, normalize_collection_name
from multi_agent_coder.tools.coding import (
    execute_create_file,
    execute_write_file,
    execute_replace_file_content,
)
from multi_agent_coder.tools.execution import (
    execute_run_command,
    execute_check_syntax,
    execute_git_status,
)
from multi_agent_coder.tools.outline import execute_get_file_outline


class TestEndToEndInfrastructureAndTools(unittest.TestCase):
    """End-to-end integration tests for infrastructure, memory, coding, execution, and outline tools."""

    def setUp(self):
        # Create a temporary directory mimicking a repo
        self.test_dir = tempfile.mkdtemp(prefix="agent_test_repo_")
        self.repo_name = Path(self.test_dir).name
        self.repo_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_token_tracker_and_logging(self):
        """Verify token tracking and logging configuration."""
        logger = setup_logging("test_logger")
        self.assertIsNotNone(logger)

        log_csv = self.repo_path / "tokens.csv"
        tracker = GeminiTokenTracker(csv_path=log_csv, model="gemini-2.0-flash")

        class MockUsageMetadata:
            prompt_token_count = 120
            candidates_token_count = 45
            total_token_count = 165

        tracker.track(MockUsageMetadata(), demo_name="Test")
        self.assertEqual(tracker.total_prompt_tokens, 120)
        self.assertEqual(tracker.total_candidate_tokens, 45)
        self.assertEqual(tracker.total_tokens, 165)
        self.assertTrue(log_csv.exists())

    def test_02_memory_store_singular_and_plural_normalization(self):
        """Verify that memory store accepts both singular and plural categories seamlessly."""
        mem_file = self.repo_path / "memory.json"
        store = MemoryStore(path=mem_file)

        res1 = store.save("fact", "Python 3.11 is used")
        res2 = store.save("insights", "ChromaDB uses cosine metric")
        res3 = store.save("preference", "Prefer concise diffs")
        res4 = store.save("invalid_cat", "Should fail")

        self.assertIn("Saved facts:", res1)
        self.assertIn("Saved insights:", res2)
        self.assertIn("Saved preferences:", res3)
        self.assertIn("Invalid category", res4)

        data = store.recall()
        self.assertEqual(len(data["facts"]), 1)
        self.assertEqual(len(data["insights"]), 1)
        self.assertEqual(len(data["preferences"]), 1)

    def test_03_repo_path_resolution(self):
        """Verify repository path resolution for direct and normalized names."""
        norm = normalize_collection_name("pallets/flask")
        self.assertEqual(norm, "pallets-flask")

        # Direct path check
        resolved = find_repo_path(str(self.repo_path))
        self.assertEqual(resolved, self.repo_path)

    def test_04_coding_tools_lifecycle(self):
        """Test create_file, replace_file_content, and write_file lifecycle."""
        # 1. create_file
        code_content = (
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
        )
        res_create = execute_create_file({
            "repo": str(self.repo_path),
            "filepath": "math_tool.py",
            "content": code_content,
        })
        self.assertIn("Successfully created", res_create)
        self.assertTrue((self.repo_path / "math_tool.py").exists())

        # Attempting duplicate create should fail
        res_dup = execute_create_file({
            "repo": str(self.repo_path),
            "filepath": "math_tool.py",
            "content": "duplicate",
        })
        self.assertIn("File already exists", res_dup)

        # 2. replace_file_content
        target = "        return a + b"
        replacement = "        # Add operation\n        return a + b"
        res_replace = execute_replace_file_content({
            "repo": str(self.repo_path),
            "filepath": "math_tool.py",
            "target_content": target,
            "replacement_content": replacement,
        })
        self.assertIn("Successfully updated", res_replace)
        file_text = (self.repo_path / "math_tool.py").read_text(encoding="utf-8")
        self.assertIn("# Add operation", file_text)

        # 3. write_file overwrite
        res_write = execute_write_file({
            "repo": str(self.repo_path),
            "filepath": "math_tool.py",
            "content": "# completely new content\nVERSION = '1.0'\n",
        })
        self.assertIn("Successfully updated", res_write)
        new_text = (self.repo_path / "math_tool.py").read_text(encoding="utf-8")
        self.assertIn("VERSION = '1.0'", new_text)

    def test_05_outline_and_syntax_tools(self):
        """Test get_file_outline and check_syntax on Python and JSON files."""
        py_code = (
            "class Worker:\n"
            '    """Worker service."""\n'
            "    def execute(self, task_id):\n"
            '        """Run task."""\n'
            "        pass\n\n"
            "def standalone_func():\n"
            "    return True\n"
        )
        (self.repo_path / "worker.py").write_text(py_code, encoding="utf-8")

        outline = execute_get_file_outline({
            "repo": str(self.repo_path),
            "filepath": "worker.py",
        })
        self.assertIn("class Worker", outline)
        self.assertIn("execute(self, task_id)", outline)
        self.assertIn("standalone_func()", outline)

        # Syntax check valid
        syn_ok = execute_check_syntax({
            "repo": str(self.repo_path),
            "filepath": "worker.py",
        })
        self.assertIn("Syntax valid", syn_ok)

        # Syntax check invalid
        (self.repo_path / "bad.py").write_text("def broken(:\n pass", encoding="utf-8")
        syn_bad = execute_check_syntax({
            "repo": str(self.repo_path),
            "filepath": "bad.py",
        })
        self.assertIn("SyntaxError", syn_bad)

    def test_06_execution_tools(self):
        """Test safe command execution."""
        res = execute_run_command({
            "repo": str(self.repo_path),
            "command": "python -c \"print('Hello from test command')\"",
            "timeout": 10,
        })
        self.assertIn("Exit code: 0", res)
        self.assertIn("Hello from test command", res)


if __name__ == "__main__":
    unittest.main()
