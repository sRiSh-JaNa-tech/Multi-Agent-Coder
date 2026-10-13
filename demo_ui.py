"""
Demo script showcasing the Rich Console UI for Phase 2 tools and multi-agent interactions.
"""

from common.ui import ConsoleUI

def main():
    ui = ConsoleUI()

    # 1. Main Application Banner
    ui.display_app_banner(repo="pallets/flask")

    # 2. Agent Handoff Banner
    ui.display_agent_banner(
        agent_name="navigator",
        task="Investigating route registration and blueprint dispatch architecture",
    )

    # 3. Tool Invocation: get_file_outline
    ui.display_tool_call(
        name="get_file_outline",
        args={"repo": "pallets-flask", "filepath": "src/flask/blueprints.py"},
    )
    sample_outline = (
        "Symbols in src/flask/blueprints.py:\n"
        "class Blueprint (line 72) — Represents a blueprint.\n"
        "    def __init__(self, name, import_name) (line 120) — Initialize blueprint.\n"
        "    def route(self, rule, **options) (line 185) — Register route decorator.\n"
        "    def register(self, app, options) (line 250) — Register blueprint onto app.\n"
        "def _endpoint_from_view_func(view_func) (line 310) — Generate endpoint name.\n"
    )
    ui.display_tool_result("get_file_outline", sample_outline)

    # 4. Agent Handoff: Coder Agent
    ui.display_agent_banner(
        agent_name="coder",
        task="Applying surgical patch to add custom JSON response formatting hook",
    )

    # Tool Invocation: replace_file_content
    ui.display_tool_call(
        name="replace_file_content",
        args={
            "repo": "pallets-flask",
            "filepath": "src/flask/app.py",
            "target_content": "return jsonify(data)",
            "replacement_content": "return self.make_json_response(data)",
        },
    )
    ui.display_tool_result("replace_file_content", "Successfully updated src/flask/app.py.")

    # 5. Agent Handoff: Reviewer Agent
    ui.display_agent_banner(
        agent_name="reviewer",
        task="Running syntax verification and pytest test suite on modified files",
    )

    # Tool Invocation: check_syntax
    ui.display_tool_call(
        name="check_syntax",
        args={"repo": "pallets-flask", "filepath": "src/flask/app.py"},
    )
    ui.display_tool_result("check_syntax", "Syntax valid for Python file: src/flask/app.py")

    # Tool Invocation: run_command
    ui.display_tool_call(
        name="run_command",
        args={"command": "pytest tests/test_basic.py -q", "repo": "pallets-flask"},
    )
    sample_cmd_output = (
        "Exit code: 0\n\n"
        "STDOUT:\n"
        "..............................                                           [100%]\n"
        "30 passed in 1.42s"
    )
    ui.display_tool_result("run_command", sample_cmd_output)

    # Tool Invocation: git_diff
    ui.display_tool_call(
        name="git_diff",
        args={"repo": "pallets-flask"},
    )
    sample_diff = (
        "diff --git a/src/flask/app.py b/src/flask/app.py\n"
        "--- a/src/flask/app.py\n"
        "+++ b/src/flask/app.py\n"
        "@@ -102,3 +102,3 @@\n"
        "-        return jsonify(data)\n"
        "+        return self.make_json_response(data)\n"
    )
    ui.display_tool_result("git_diff", sample_diff)

    # 6. Final Agent Response
    ui.display_agent_response(
        "reviewer",
        "### Review Completed Successfully\n\n"
        "- **Syntax Check**: Passed without warnings.\n"
        "- **Test Suite**: 30/30 tests passed (`tests/test_basic.py`).\n"
        "- **Diff Verification**: Clean, surgical 1-line update cleanly applied.\n\n"
        "The codebase is healthy and ready for deployment."
    )

if __name__ == "__main__":
    main()
