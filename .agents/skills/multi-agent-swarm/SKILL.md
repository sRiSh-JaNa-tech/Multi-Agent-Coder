---
name: multi-agent-swarm
description: Orchestrate the local Multi-Agent Coder worker swarm as the Lead Cognitive Brain. Dispatches DAG tickets, coordinates git worktrees, inspects diffs, and approves safe merges.
---

# Multi-Agent Swarm Orchestration Skill

When the user asks you to implement complex features, refactor codebases, or coordinate engineering tasks using the multi-agent system, **you act as the Lead Cognitive Brain (The Architect)**. The local `Multi-Agent Coder` fleet (Agent-1 through Agent-5) works under your direction as specialized execution units.

---

## 1. Roles & Separation of Concerns

* **The Brain (Antigravity)**:
  * High-level architectural reasoning and requirement decomposition.
  * Constructing Directed Acyclic Graphs (DAGs) of tickets with Kahn's topological ordering.
  * Reviewing code patches in isolated Git worktrees (`.worktrees/ticket-<id>`).
  * Safety gating, running regression tests, and approving final merges to `main`.

* **The Worker Fleet (`multi_agent_coder`)**:
  * **Agent-1** (Analysis): AST search, repo indexing, symbol mapping.
  * **Agent-2** (Coding): Core feature implementation, surgical AST replacement.
  * **Agent-3** (Testing): Sandbox test writing and automated test execution.
  * **Agent-4** (Refactor): AST verification, code restructuring.
  * **Agent-5** (Docs): Architectural documentation and markdown generation.

---

## 2. Execution Modes

You have two primary ways to dispatch tasks to the swarm:

### Method A: Native MCP Server Tools
The workspace exposes the `MultiAgentCoderSwarm` MCP server with the following tools:
1. `swarm_submit_dag(tickets, objective, max_agents)`:
   Submit an explicit DAG of tickets directly without relying on heuristic LLM breakdown.
2. `swarm_dispatch_objective(objective, max_agents)`:
   Submit an objective and let the internal orchestrator decompose and execute it.
3. `swarm_status()`:
   Inspect active worktrees, branches, and worker queue depths.
4. `swarm_get_worktree_diff(ticket_id)`:
   Fetch the exact Git diff generated in `.worktrees/ticket-<ticket_id>` for your architectural review.
5. `swarm_merge_worktree(ticket_id, target_branch)`:
   Merge the approved changes into `main` and clean up the worktree.

### Method B: Headless CLI Runner (Background Tasks)
When MCP is connecting or for batch terminal pipelines:
```powershell
python -m multi_agent_coder.cli.orchestrator --manifest data/tickets.json --headless --output data/runs/summary.json
```

---

## 3. Standard Brain Workflow

1. **Deconstruct Request**:
   Divide the user's task into 2 to 5 discrete tickets. Ensure prerequisites are reflected in `depends_on`.
   
   Example Ticket Schema:
   ```json
   [
     {
       "id": "TICK-001",
       "title": "Analyze existing auth handler",
       "description": "Inspect auth tokens and find security gaps",
       "category": "analysis",
       "depends_on": []
     },
     {
       "id": "TICK-002",
       "title": "Implement JWT rotation logic",
       "description": "Add refresh token rotation in auth/jwt.py",
       "category": "coding",
       "depends_on": ["TICK-001"]
     },
     {
       "id": "TICK-003",
       "title": "Write unit tests for token expiry",
       "description": "Add pytest tests in tests/test_auth.py",
       "category": "testing",
       "depends_on": ["TICK-002"]
     }
   ]
   ```

2. **Dispatch & Monitor**:
   Send the manifest to `swarm_submit_dag`. The agents execute synchronously one-by-one inside dedicated worktrees:
   * Branch: `agent/ticket-<id>`
   * Path: `.worktrees/ticket-<id>`

3. **Audit & Review**:
   Inspect the diff using `swarm_get_worktree_diff(ticket_id="TICK-002")`.
   Ensure no path traversal, syntax breaks, or secret leaks exist.

4. **Merge & Report**:
   Call `swarm_merge_worktree(ticket_id="TICK-002")` to merge into `main`.
   Present the final status and code summary to the user.
