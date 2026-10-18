"""
Runner script to launch the 8-agent swarm across the 10-phase upgrade DAG.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Ensure src is on sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from multi_agent_coder.orchestrator.main_orchestrator import MainOrchestrator

def main():
    manifest_path = Path("data/manifests/production_swarm_upgrade_dag.json")
    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Loaded manifest with {len(manifest.get('tickets', []))} tickets.")
    print("Initializing MainOrchestrator with 8 agents (7 workers + 1 QA Tester)...")

    orch = MainOrchestrator(
        max_agents=8,
        queue_limit_per_agent=3,
        workspace_root=".",
        parallel=True,
        auto_qa=True,
    )

    tickets = orch.load_manifest(manifest)
    print(f"Successfully loaded and validated {len(tickets)} DAG tickets.")
    print(f"Designated QA Tester: {orch.tester_agent.agent_id if orch.tester_agent else 'None'}")
    print(f"Worker agents count: {len(orch.worker_agents)}")

    print("\nStarting execution of all 10 phases across the 8-agent swarm...")
    results = orch.process_all_tickets()

    summary = orch.get_summary()
    print("\n=== SWARM EXECUTION SUMMARY ===")
    print(f"Total tickets: {summary.get('total_tickets')}")
    print(f"Resolved: {summary.get('resolved')}")
    print(f"Failed: {summary.get('failed')}")
    print(f"Blocked: {summary.get('blocked')}")
    print(f"Run ID: {summary.get('run_id')}")

    # Print outcome per ticket
    for t in summary.get("tickets", []):
        print(f"  [{t.get('status')}] {t.get('id')}: {t.get('title')} (Agent: {t.get('assigned_agent_id')}, Tool Calls: {t.get('tool_calls')})")

if __name__ == "__main__":
    main()
