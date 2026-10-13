# Multi-Agent Coder

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Google Gemini](https://img.shields.io/badge/Model-Gemini%202.5%20Flash%20Lite-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![SDK](https://img.shields.io/badge/SDK-google--genai-blue?style=flat-square)](https://github.com/googleapis/python-genai)
[![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-purple?style=flat-square)](https://www.trychroma.com/)
[![Rich UI](https://img.shields.io/badge/CLI-Rich%20Terminal-green?style=flat-square)](https://github.com/Textualize/rich)

An intelligent agentic AI coding suite powered by **Google Gemini** (`gemini-2.5-flash-lite` via `google-genai`). Features an autonomous **Codebase Navigator & Coding Agent** equipped with 16 autonomous tools, semantic RAG, cross-session memory, and a dynamic Rich console interface, alongside structured foundations and tutorials.

---

## Repository Structure

```
Multi-Agent-Coder/
├── 01_codebase_navigator.py       # Root entrypoint (routes to codebase-navigator)
├── pyproject.toml                 # Root project configuration and dependencies
├── README.md                      # Primary project documentation
│
├── codebase-navigator/            # Core Autonomous Codebase Navigator & Agent
│   ├── 01_codebase_navigator.py   # Main agentic loop with ReAct orchestration
│   ├── demo_ui.py                 # Live terminal demonstration of Rich UI components
│   ├── test_e2e_tools.py          # End-to-end integration test suite (6/6 passing)
│   ├── pyproject.toml             # Package metadata
│   ├── README.md                  # Detailed module architecture & guide
│   ├── common/                    # Shared infrastructure
│   │   ├── logging_config.py      # Standardized logging setup
│   │   ├── menu.py                # Interactive terminal repository selector
│   │   ├── token_tracker.py       # GeminiTokenTracker (cost & token metrics)
│   │   └── ui.py                  # ConsoleUI (panels, banners, markdown streams)
│   ├── indexer/                   # Ingestion & Embedding Pipeline
│   │   ├── chunker.py             # AST-aware code chunking (functions/classes)
│   │   └── embedder.py            # Gemini text-embedding-004 + ChromaDB pipeline
│   ├── store/                     # Persistent Storage Layer
│   │   ├── memory.py              # Long-term JSON memory store (facts/insights)
│   │   └── vector.py              # ChromaDB vector store wrapper
│   └── tools/                     # Autonomous Agent Tool Registry (16 tools)
│       ├── coding.py              # create_file, write_file, replace_file_content
│       ├── execution.py           # run_command, check_syntax, git_diff, git_status
│       ├── files.py               # read_file, list_directory
│       ├── memory.py              # save_memory, recall_memory
│       ├── outline.py             # get_file_outline (AST structure)
│       ├── repo.py                # clone_and_index, list_repos
│       └── search.py              # search_code, grep
│
└── examples/                      # Foundational Gemini Agent Tutorials
    ├── README.md                  # Guide for examples
    ├── gemini_prompting.py        # Zero-shot, system prompts, role definition
    ├── gemini_few_shot_cot.py     # Few-shot exemplars & chain-of-thought reasoning
    ├── structured_output_gemini.py# Strict schema enforcement & Pydantic output
    ├── tool_use_gemini.py         # Autonomous function calling basics
    └── gemini_coding_agent.py     # Single-file ReAct coding assistant
```

---

## Key Modules & Features

### 1. Codebase Navigator (`codebase-navigator/`)
- **Semantic Retrieval (RAG)**: Automatically clones GitHub repositories, extracts code chunks using AST awareness, embeds them using `text-embedding-004`, and indexes them in ChromaDB.
- **Developer Tool Suite (16 Tools)**:
  - *Code Modification*: Create files, replace code blocks, inspect diffs.
  - *Execution & Testing*: Run test commands in isolated subprocesses and validate Python syntax.
  - *Structure Inspection*: Generate hierarchical class and function outlines with line counts.
- **Cross-Session Memory**: Automatically remembers architectural decisions, repository quirks, and preferences across sessions in `data/memory.json`.
- **Rich Terminal UI**:
  - Gradient banner headers
  - Live tool-call spinners and structured result panels
  - Markdown-rendered responses with syntax-highlighted code blocks
- **Automatic API Key Prompting**: If `GEMINI_API_KEY` is not present in the environment or `.env`, the agent prompts the user securely in the terminal and persists it to `.env`.

### 2. Gemini Foundations (`examples/`)
Hands-on, self-contained examples demonstrating standard patterns in LLM orchestration:
- **Prompt Engineering**: Zero-shot vs system instructions.
- **Chain of Thought**: Step-by-step reasoning prompts.
- **Structured Outputs**: Guarantees JSON conformance matching Pydantic schemas.
- **Tool Calling**: Binding Python functions to Gemini function declarations.

---


### 3. Multi-Agent Ticket Orchestration (`02_ticket_orchestrator.py`)
- **Main Orchestrator**: Identifies problems from user objectives, generates discrete problem tickets, and matches them to specialized agents (`analysis`, `coding`, `testing`).
- **Strict Queue Limit (3 Tickets)**: Each agent maintains a queue with a hard limit of 3 tickets. Excess tickets remain in master backlog until queue slots open.
- **Synchronous Processing**: Agents execute tickets **one by one synchronously** in strict FIFO sequence.
- **Live Visual Dashboard**: Rich terminal table monitoring agent queues, active tickets, and real-time resolution logs.

---


### 4. Pluggable LLM Harness (`03_llm_harness_demo.py` / `codebase-navigator/harness/`)
- **Adapter-Agnostic Engine**: Quickly attach **any LLM backend** (`MockLLMAdapter`, `CallableAdapter`, `GeminiAdapter`, `OpenAICompatibleAdapter`) to run agentic tool execution.
- **Isolated from Main API**: Runs as a separate testing/execution subsystem—zero risk of breaking the main working agent.
- **Synchronous Ticket Worker (`HarnessTicketWorker`)**: Allows multi-agent ticket execution powered by attached custom models or offline mocks.
- **Deterministic 0-Cost Testing**: `MockLLMAdapter` allows instant multi-turn tool calling and ReAct loop verification without API tokens or network latency.

```bash
# Run the interactive harness demo
python 03_llm_harness_demo.py

# Run harness unit & integration tests
python codebase-navigator/test_harness.py
```

## Quickstart

### 1. Prerequisites
- Python 3.11 or higher
- Git

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/sRiSh-JaNa-tech/Multi-Agent-Coder.git
cd Multi-Agent-Coder

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r pyproject.toml
```

### 3. Configure Gemini API Key
You can either set the environment variable:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY = "your-gemini-api-key"

# Linux / macOS
export GEMINI_API_KEY="your-gemini-api-key"
```
Or simply run the agent—it will prompt you interactively on first launch and save it to `.env` automatically!

---

## Usage

### Run the Codebase Navigator
From the project root:
```bash
python 01_codebase_navigator.py
```
Or from within the module directory:
```bash
cd codebase-navigator
python 01_codebase_navigator.py
```

### Run the Terminal UI Demo
Preview the styling, badges, and response format:
```bash
python codebase-navigator/demo_ui.py
```

### Run End-to-End Tests
Execute the full integration test suite:
```bash
python codebase-navigator/test_e2e_tools.py
```

### Run Foundation Examples
Explore standalone Gemini lessons:
```bash
python examples/gemini_prompting.py
python examples/gemini_few_shot_cot.py
python examples/structured_output_gemini.py
python examples/tool_use_gemini.py
python examples/gemini_coding_agent.py
```

---

## License
MIT License.
