"""Unified CLI Entrypoint for Multi-Agent Coder."""
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        prog="multi-agent-coder",
        description="Multi-Agent Coder: Autonomous Concurrent Engineering System"
    )
    parser.add_argument("command", choices=["navigator", "orchestrator", "harness"],
                        help="Subcommand to run")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to subcommand")

    args = parser.parse_args()

    if args.command == "navigator":
        from multi_agent_coder.cli import navigator
        sys.argv = [sys.argv[0]] + args.args
        navigator.main()
    elif args.command == "orchestrator":
        from multi_agent_coder.cli import orchestrator
        sys.argv = [sys.argv[0]] + args.args
        orchestrator.main()
    elif args.command == "harness":
        from multi_agent_coder.cli import harness_demo
        sys.argv = [sys.argv[0]] + args.args
        harness_demo.main()

if __name__ == "__main__":
    main()
