# Multi-Agent Coder

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Google Gemini](https://img.shields.io/badge/Model-Gemini%202.5%20Flash%20Lite-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![SDK](https://img.shields.io/badge/SDK-google--genai-blue?style=flat-square)](https://github.com/googleapis/python-genai)
[![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-purple?style=flat-square)](https://www.trychroma.com/)
[![Rich UI](https://img.shields.io/badge/CLI-Rich%20Terminal-green?style=flat-square)](https://github.com/Textualize/rich)
[![Pytest](https://img.shields.io/badge/Tests-69%2F69%20Passing-brightgreen?style=flat-square)](https://docs.pytest.org/)

An enterprise-grade, fault-tolerant concurrent multi-agent engineering system powered by **Google Gemini** (`gemini-2.5-flash-lite` via `google-genai`). Features DAG dependency orchestration, multi-threaded parallel agent execution, dedicated Nth-agent QA verification, Git worktree isolation, surgical atomic code editing, sandboxed execution with secret stripping, circuit-breaker guards, and an automated verification test suite.

---

## System Architecture

```mermaid
graph TB
    subgraph ClientLayer ["Client & Interface Layer"]
        CLI["CLI Command (multi-agent-coder)"]
        MCP["MCP Protocol Server (multi-agent-coder MCP)"]
        BRAIN["Lead Brain / Antigravity AI"]
    end

    subgraph OrchestratorCore ["Main Orchestrator Core"]
        DAG["Ticket DAG Engine (Kahn's Topological Sort)"]
        BUDGET["Token Budget Manager (Thread-Safe Ceiling)"]
        ROSTER["Agent Roster & Reroute Logic (Worker Pool vs Tester)"]
        PARALLEL["Parallel Worker ThreadPoolExecutor"]
        LOGGER["Structured Run Logger (events.jsonl & summary.json)"]
    end

    subgraph SwarmFleet ["Concurrent Agent Fleet (MAX_AGENTS = N)"]
        subgraph Workers ["Worker Pool (Agents 1 to N-1)"]
            A1["Agent-1: Code Navigator & System Analyst"]
            A2["Agent-2: Core Implementation Engineer"]
            A3["Agent-3: Refactoring & Performance Engineer"]
            A4["Agent-4: Documentation & Architecture Specialist"]
        end
        subgraph QA_Tester ["Dedicated QA Gate (Agent-N)"]
            AN["Agent-N: Lead QA & Test Verification Engineer"]
        end
    end

    subgraph SafetyAndTools ["Tool Execution & Safety Sandbox"]
        TOOLS["Surgical File Tools (Exact Replace, Read)"]
        SYNTAX["Multi-Language Syntax Gate (AST / node --check)"]
        EXEC["Sandboxed Command Execution (Secret Stripping & Timeouts)"]
        GUARD["ExecutionGuard Circuit Breaker (Loop Detection & Auto-Retry)"]
    end

    subgraph Workspace ["Target Workspace (In-Place Mutation)"]
        TARGET["Target Project Repository (e.g. FileWiz / App)"]
    end

    CLI --> DAG
    MCP --> DAG
    BRAIN --> DAG

    DAG --> ROSTER
    ROSTER --> BUDGET
    BUDGET --> PARALLEL

    PARALLEL -.->|Concurrent Dispatch| A1
    PARALLEL -.->|Concurrent Dispatch| A2
    PARALLEL -.->|Concurrent Dispatch| A3
    PARALLEL -.->|Concurrent Dispatch| A4

    A2 -->|Code Patches Completed| AN
    A3 -->|Refactor Patches Completed| AN

    A1 --> TOOLS
    A2 --> TOOLS
    A3 --> TOOLS
    A4 --> TOOLS
    AN --> SYNTAX
    AN --> EXEC

    TOOLS --> GUARD
    SYNTAX --> GUARD
    EXEC --> GUARD

    GUARD --> TARGET
    AN -->|Verified Test Pass & Zero Regressions| LOGGER
```

---

## End-to-End Operational Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Lead Brain
    participant Orch as Main Orchestrator
    participant DAG as Ticket DAG Engine
    participant Workers as Worker Agents (1 to N-1)
    participant QA as QA Tester (Agent-N)
    participant Target as Target Workspace

    User->>Orch: Submit Objective or Manifest DAG
    Orch->>DAG: Ingest & Decompose into Discrete Tickets
    DAG->>DAG: Kahn's Algorithm Validation (Cycle Detection)
    
    rect rgb(240, 248, 255)
        note over Orch,Workers: Parallel Concurrent Execution Phase
        Orch->>Workers: Dispatch Ready Work Tickets to Idle Agents (Queues <= 3)
        par Concurrent Worker Tasks
            Workers->>Target: Explore & Inspect Codebase
            Workers->>Target: Surgical Search/Replace Code Modifications
            Workers->>Target: Run Local Syntax Verification
            Workers-->>Orch: Report [Agent Status: RESOLVED]
        end
    end

    rect rgb(255, 245, 238)
        note over Orch,QA: Automated Nth-Agent QA Testing Phase
        Orch->>QA: Dispatch QA Verification Ticket (Depends on Worker Tickets)
        QA->>Target: Inspect Git Diffs & Status
        QA->>Target: Run check_syntax on All Modified Files
        QA->>Target: Execute Automated Test Suites (pytest / npm test)
        QA-->>Orch: Report Verified Test Results & Regression Checks
    end

    Orch->>User: Final Summary Report (All Tickets Resolved, Full Audit Trail)
```

### Detailed Workflow Stages

1. **Objective Ingestion & DAG Decomposition**:
   - The user or Lead Brain passes an objective (e.g. `--objective "Optimize database & add benchmarks"`) or a structured manifest DAG (`--manifest path/to/dag.json`).
   - The Orchestrator decomposes the problem into discrete technical tickets (`analysis`, `coding`, `refactor`, `testing`).
   - Dependencies are validated with **Kahn's topological sort** to eliminate cycles upfront.

2. **Parallel Scheduling & Dynamic Dispatching**:
   - Tickets with satisfied prerequisites enter the dispatch queue.
   - The Orchestrator enforces a strict per-agent queue limit of 3.
   - Ready tickets are routed dynamically across idle worker agents (`queue_size == 0`) to maximize fleet concurrency.
   - Work tickets execute in parallel using multi-threaded execution (`ThreadPoolExecutor`).

3. **In-Place Surgical Editing & Sandboxed Tools**:
   - Agents operate directly within the target workspace without creating duplicate repos.
   - File edits use strict context-anchored search/replace patterns with duplicate block rejection.
   - Every file change is immediately validated by the syntax checker (`node --check` for JS, `ast.parse` for Python).
   - `ExecutionGuard` prevents infinite tool loops and automatically retries transient API errors.

4. **Nth-Agent QA Verification & Reporting**:
   - For an agent pool of size $N$ (e.g., 5 agents): Agents 1 to $N-1$ (Agents 1-4) execute implementation tasks, while Agent $N$ (Agent-5) is strictly reserved as the **Lead QA & Test Verification Engineer**.
   - Completed code changes trigger an automated QA ticket for Agent $N$.
   - Agent $N$ runs regression test suites (`pytest`, `npm test`, `node tests/e2e.test.js`) and reports pass/fail verification logs directly to the Orchestrator.

---

## Unified Repository Layout

```
Multi-Agent-Coder/
├── pyproject.toml              # Unified package configuration & pytest settings
├── uv.lock                     # Unified lockfile
├── .env.example                # Example environment variables
├── src/
│   └── multi_agent_coder/      # Core source package
│       ├── __init__.py
│       ├── cli/                # Consolidated CLI subcommands (navigator, orchestrator, harness)
│       │   ├── __init__.py
│       │   ├── __main__.py     # Unified entrypoint: multi-agent-coder <subcommand>
│       │   ├── navigator.py    # Codebase Navigator agent
│       │   ├── orchestrator.py # Multi-agent ticket orchestrator
│       │   └── harness_demo.py # Pluggable LLM harness demo
│       ├── common/             # logging_config.py, menu.py, token_tracker.py (ExecutionGuard), ui.py
│       ├── harness/            # adapters.py, base.py, engine.py, ticket_runner.py, types.py
│       ├── indexer/            # chunker.py, embedder.py
│       ├── orchestrator/       # agent_worker.py, dashboard.py, main_orchestrator.py, ticket.py (TicketDAG)
│       ├── store/              # memory.py, vector.py
│       └── tools/              # coding.py (atomic patch), execution.py (sandboxed), files.py, repo.py (worktree)
└── tests/                      # Dedicated pytest test suite (29 tests)
    ├── conftest.py
    ├── test_dag_orchestrator.py
    ├── test_surgical_coding.py
    ├── test_sandbox_execution.py
    ├── test_harness_circuit_breaker.py
    ├── test_worktree_isolation.py
    ├── test_ticket_system.py
    ├── test_harness.py
    └── test_e2e_tools.py
```

---

## Threat Model & Failure Mode Mitigations

| Subsystem | Threat / Failure Mode | Hardened Mitigation |
| :--- | :--- | :--- |
| **Orchestrator** (`ticket.py`, `main_orchestrator.py`) | Circular dependencies, deadlocks, hanging child tasks | **Kahn's topological sort** on ticket ingestion rejects cycles immediately. Downstream tickets transition to `BLOCKED` if any dependency fails. |
| **Concurrency** (`agent_worker.py`, `tools/repo.py`) | Race conditions & dirty working trees between agents | **Git Worktree Isolation**: Each ticket runs in `.worktrees/ticket-<id>` on its own branch (`agent/ticket-<id>`). Startup auto-prunes stale worktrees. |
| **Code Editing** (`tools/coding.py`, `tools/files.py`) | Path traversal attacks, hallucinated line numbers, broken syntax | Strict **SEARCH/REPLACE** exact matching, workspace root boundary check (`is_relative_to`), in-memory Python AST validation (`ast.parse`), and atomic write via tempfile + `os.replace`. |
| **Execution** (`tools/execution.py`) | Zombie processes, hanging input prompts, context window overflow | `stdin=subprocess.DEVNULL`, process-group isolation, secret stripping (`API_KEY`, `TOKEN`, `PASSWORD`), hard timeouts with process tree termination, and output head/tail truncation. |
| **Harness & Spend** (`harness/engine.py`, `token_tracker.py`) | Infinite tool loops, rate limits, runaway token cost | **ExecutionGuard Circuit Breaker**: State-hash deduplication trips after 3 identical tool calls. Hard token budget ceiling aborts execution if spend limit reached. |

---

## Quickstart & CLI

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/sRiSh-JaNa-tech/Multi-Agent-Coder.git
cd Multi-Agent-Coder

# Install in editable mode
pip install -e .
```

### 2. Configure Environment
```bash
cp .env.example .env
# Set your GEMINI_API_KEY and MAX_AGENTS=3
```

### 3. Run Subcommands via Unified CLI
```bash
# Launch Codebase Navigator
multi-agent-coder navigator

# Launch Multi-Agent Ticket Orchestrator
multi-agent-coder orchestrator

# Launch LLM Testing & Execution Harness Demo
multi-agent-coder harness
# Or run non-interactive automated harness demos:
multi-agent-coder harness --all
```

---

## Automated Pytest Verification Suite

Run all 69 automated tests across DAG orchestration, parallel execution, Nth-agent QA verification, surgical coding, sandboxed execution, worktree isolation, and circuit breakers:

```bash
pytest tests/ -v
```

### Test Suite Coverage (69 Tests):
- `tests/test_parallel_and_tester.py`: Multi-threaded parallel execution concurrency overlap, dedicated Nth-agent QA tester designation (Agent-5 when `MAX_AGENTS=5`), automated QA verification ticket generation.
- `tests/test_swarm_controls.py`: Environment variable controls (`MODEL_NAME`, `TOKEN_USAGE_LIMIT`, `TARGET_WORKSPACE`), thread-safe token budget enforcement, git push worker guard, honest failure reporting.
- `tests/test_dag_orchestrator.py`: Cycle detection with Kahn's algorithm, missing dependency validation, downstream failure blocking.
- `tests/test_ticket_system.py`: Multi-agent FIFO queue execution, 3-ticket per agent strict queue limit, backlog dispatching.
- `tests/test_surgical_coding.py`: Path traversal protection, atomic file edits, syntax validation gates, duplicate block rejection.
- `tests/test_sandbox_execution.py`: Process timeout killing, secret stripping from environment, output head/tail truncation.
- `tests/test_harness_circuit_breaker.py`: Repeated identical tool call deduplication, token budget ceiling enforcement.
- `tests/test_worktree_isolation.py`: Isolated branch lifecycle, conflict-free parallel worktree editing and merge back to main.
- `tests/test_api_key_validation.py`: Secure API key acquisition, missing key rejection, mock environments.
- `tests/test_harness.py`: Mock, Callable, and Gemini adapter integrations.
- `tests/test_e2e_tools.py`: End-to-end tool registry operations.
- `tests/test_mcp_and_manifest.py`: MCP tool definitions, JSON manifest loading and validation.
