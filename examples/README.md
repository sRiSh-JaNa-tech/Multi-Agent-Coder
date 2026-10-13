# Gemini Agentic AI Examples

This directory contains foundational scripts and lessons demonstrating core agentic patterns using the Google Gemini API (`google-genai` SDK) and `gemini-2.5-flash-lite`.

---

## Available Examples

| Script | Concept | Description |
| :--- | :--- | :--- |
| `gemini_prompting.py` | **Prompt Engineering** | Zero-shot prompting, system instructions, and interactive CLI selection. |
| `gemini_few_shot_cot.py` | **Few-Shot & Chain-of-Thought** | Step-by-step reasoning prompts with exemplars for complex problem solving. |
| `structured_output_gemini.py` | **Structured Outputs** | Enforcing strict JSON schemas and Pydantic validation on model responses. |
| `tool_use_gemini.py` | **Function Calling** | Declaring functions, executing tool calls, and feeding results back to Gemini. |
| `gemini_coding_agent.py` | **ReAct Loop Agent** | Autonomous multi-turn coding agent loop with tool orchestration. |

---

## How to Run

Ensure your virtual environment is active and `GEMINI_API_KEY` is configured:

```bash
# Run any example directly:
python examples/gemini_prompting.py
python examples/gemini_few_shot_cot.py
python examples/structured_output_gemini.py
python examples/tool_use_gemini.py
python examples/gemini_coding_agent.py
```
