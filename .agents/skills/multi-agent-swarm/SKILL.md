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

### REA Reverse Engineering Support

REA is registered as the `rea` MCP server for Codex, and its reverse-engineering tools are also exposed to swarm workers as `rea_list_tools` and `rea_call_tool`. The matching skill is installed in the user skill directory. Restart Codex to load its MCP server and skill; workers start their own REA MCP session when they use the bridge tools.

For a challenge, let REA and the workers inspect supplied artifacts, follow promising evidence, and create helper scripts or notes inside the challenge workspace when useful. Preserve the original challenge files. Convert findings into tickets when coordination helps; workers may investigate independently and verify one another's claims without waiting for the lead to relay every REA result.

Workers can discover REA's current tools with `rea_list_tools(query, include_schemas)`. Use a focused query such as `binary`, `APK`, or `packet` with `include_schemas=true` to retrieve the matching input schemas, then call the selected operation with `rea_call_tool(tool_name, arguments)`. The lead may pass prior findings into tickets to avoid duplicate work, while workers can independently verify them or continue the investigation. The bridge launches the configured REA MCP command (default `npx -y rea-agents@6.7.0 mcp`); set `REA_MCP_COMMAND`, `REA_MCP_ARGS` (JSON string array), or `REA_MCP_VERSION` to select another installed command or version.

On Linux, several REA workflows require a procps-compatible `ps` on `PATH`. Native binary analysis also needs a configured provider such as Ghidra, Hopper, or IDA. Treat unavailable providers as a capability limit and use the tools available for the challenge.

You have two primary ways to dispatch tasks to the swarm:

### Method A: Native MCP Server Tools
The workspace exposes the `MultiAgentCoderSwarm` MCP server with the following tools:
1. `swarm_submit_dag(tickets, objective, max_agents, workspace, token_limit)`:
   Submit an explicit DAG of tickets directly without relying on heuristic LLM breakdown.
2. `swarm_dispatch_objective(objective, max_agents, workspace, token_limit)`:
   Submit an objective and let the internal orchestrator decompose and execute it.
3. `swarm_status(workspace)`:
   Inspect workspace, model, token limit, log dir, recent runs, worktrees and queue config.
4. `swarm_get_run_log(run_id, tail)`:
   Audit trail: tickets created/assigned/failed/blocked, tool calls, token usage.
5. `swarm_get_worktree_diff(ticket_id, workspace)`:
   Fetch the exact Git diff generated in `.worktrees/ticket-<ticket_id>` for your architectural review.
6. `swarm_merge_worktree(ticket_id, target_branch, workspace)`:
   Merge the approved changes into `main` and clean up the worktree.

> **Always pass `workspace` = the real target project (or set `TARGET_WORKSPACE` in `.env`).**
> The swarm edits it in place. Never copy a project into this repo and never push a copied
> project to this repo's remote. Workers cannot commit/push; you review and commit in the target repo.

**Full operating manual** (agent naming, ticket template, DAG rules, token budget, failure codes,
supervision loop): `python -m multi_agent_coder.orchestrator.brain_prompt` -
[brain_prompt.py](../../../src/multi_agent_coder/orchestrator/brain_prompt.py). It is also served as the MCP server instructions.

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
