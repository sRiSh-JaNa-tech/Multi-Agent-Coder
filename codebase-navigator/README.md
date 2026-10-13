# Codebase Navigator & Coding Agent

An autonomous augmented LLM agent designed to explore, understand, edit, and test codebases using **Google Gemini** (`google-genai` SDK, `gemini-2.5-flash-lite`), **ChromaDB**, and a rich suite of developer tools.

---

## Architecture Overview

The agent implements the **Augmented LLM** pattern:

```
                      +-----------------------------------+
                      |      Gemini 2.5 Flash Lite        |
                      +-----------------+-----------------+
                                        |
                 +----------------------+----------------------+
                 |                      |                      |
                 v                      v                      v
        +----------------+     +----------------+     +----------------+
        | Retrieval (RAG)|     | Memory Store   |     | Tool Registry  |
        |  ChromaDB +    |     | Cross-session  |     |  16 Autonomous |
        |  Embeddings    |     | Knowledge base |     |  Tools         |
        +----------------+     +----------------+     +----------------+
```

### The Three Augmentations:
1. **Retrieval (RAG)**: Indexes code repositories into AST-aware chunks, creates vector embeddings via Gemini `text-embedding-004`, and performs semantic search using ChromaDB.
2. **Cross-Session Memory**: Stores architecture patterns, key files, and user preferences into `data/memory.json` to retain insights across runs.
3. **Tool Execution Loop**: An autonomous multi-turn ReAct loop that executes tool calls and feeds results back to Gemini.

---

## Tool Capabilities

| Category | Tools | Description |
| :--- | :--- | :--- |
| **Repository** | `clone_and_index`, `list_repos` | Clones any public GitHub repo and indexes into ChromaDB. |
| **Search & Navigation** | `search_code`, `grep`, `read_file`, `list_directory` | Semantic vector search, regex grep, and filesystem inspection. |
| **Code Inspection** | `get_file_outline` | AST-based class, function, and method outlines with line numbers. |
| **Coding & Editing** | `create_file`, `write_file`, `replace_file_content` | Precision file modifications and content substitution. |
| **Execution & Testing** | `run_command`, `check_syntax`, `git_diff`, `git_status` | Shell command execution, syntax validation, and git review. |
| **Memory** | `save_memory`, `recall_memory` | Save and query long-term facts, architecture insights, and user preferences. |

---

## Setup & Running

### 1. Requirements
- Python 3.11+
- Virtual environment with dependencies installed:
  ```bash
  pip install -r pyproject.toml
  # or using uv:
  uv sync
  ```

### 2. Run the Navigator
```bash
python 01_codebase_navigator.py
```
> **API Key Prompting**: If `GEMINI_API_KEY` is not present in your environment, the agent will prompt you in the terminal and save it to `.env` automatically.

### 3. Demo the UI
```bash
python demo_ui.py
```

### 4. Run End-to-End Tests
```bash
python test_e2e_tools.py
```
