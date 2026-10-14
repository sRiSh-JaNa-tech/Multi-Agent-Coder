"""
LLM Adapters for the Agentic Harness.
Provides concrete implementations of BaseLLMAdapter for:
- MockLLMAdapter (offline, scripted tool calling, 0-cost testing)
- CallableAdapter (wrap any custom Python function or lambda)
- GeminiAdapter (official Google GenAI SDK integration)
- OpenAICompatibleAdapter (OpenAI, Ollama, vLLM, DeepSeek, LocalAI)
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from .base import BaseLLMAdapter
from .types import LLMResponse, Message, TokenUsage, ToolCall, ToolResult


class MockLLMAdapter(BaseLLMAdapter):
    """
    Offline Mock LLM Adapter for fast deterministic testing and CI/CD.
    Can be configured with pre-scripted responses or a dynamic response handler.
    """

    def __init__(
        self,
        responses: list[LLMResponse | str | dict[str, Any]] | None = None,
        handler: Callable[[list[Message], list[dict[str, Any]] | None], LLMResponse] | None = None,
        model_name: str = "mock-agent-v1",
        name: str = "MockLLMAdapter",
    ):
        super().__init__(model_name=model_name, name=name)
        self.responses = list(responses) if responses else []
        self.handler = handler
        self.call_history: list[dict[str, Any]] = []

    def add_response(self, response: LLMResponse | str | dict[str, Any]) -> None:
        """Enqueue another scripted response."""
        self.responses.append(response)

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        self.call_history.append({
            "messages": messages,
            "tools": tools,
            "system_instruction": system_instruction,
        })

        if self.handler:
            return self.handler(messages, tools)

        if not self.responses:
            return LLMResponse(
                text="[MockLLMAdapter] No further scripted responses available.",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            )

        resp = self.responses.pop(0)
        if isinstance(resp, LLMResponse):
            return resp
        if isinstance(resp, str):
            return LLMResponse(
                text=resp,
                usage=TokenUsage(prompt_tokens=len(resp), completion_tokens=len(resp), total_tokens=2 * len(resp)),
            )
        if isinstance(resp, dict):
            text = resp.get("text")
            raw_calls = resp.get("tool_calls", [])
            tool_calls = []
            for c in raw_calls:
                if isinstance(c, ToolCall):
                    tool_calls.append(c)
                elif isinstance(c, dict):
                    tool_calls.append(ToolCall(name=c["name"], args=c.get("args", {})))
            return LLMResponse(
                text=text,
                tool_calls=tool_calls,
                usage=TokenUsage(prompt_tokens=20, completion_tokens=20, total_tokens=40),
            )

        return LLMResponse(text=str(resp))


class CallableAdapter(BaseLLMAdapter):
    """
    Adapter that executes an arbitrary Python callable.
    Allows developers to attach custom functions, local models, or heuristics.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        model_name: str = "custom-callable",
        name: str = "CallableAdapter",
    ):
        super().__init__(model_name=model_name, name=name)
        self.fn = fn

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        result = self.fn(messages=messages, tools=tools, system_instruction=system_instruction)
        if isinstance(result, LLMResponse):
            return result
        if isinstance(result, str):
            return LLMResponse(text=result)
        if isinstance(result, dict):
            text = result.get("text")
            calls = [
                c if isinstance(c, ToolCall) else ToolCall(name=c["name"], args=c.get("args", {}))
                for c in result.get("tool_calls", [])
            ]
            return LLMResponse(text=text, tool_calls=calls)
        return LLMResponse(text=str(result))


class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter for Google Gemini models via google-genai SDK.
    Supports native function calling, token counting, and system instructions.
    """

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
        name: str = "GeminiAdapter",
    ):
        super().__init__(model_name=model_name, name=name)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError:
                raise ImportError("google-genai package is required. Install via `pip install google-genai`.")

            if self.api_key:
                self._client = genai.Client(api_key=self.api_key)
            else:
                self._client = genai.Client()
        return self._client

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        from google.genai import types

        client = self._get_client()

        # Convert Unified Messages to Gemini Content format
        contents = []
        for msg in messages:
            if msg.role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg.content or "")]))
            elif msg.role == "assistant":
                parts = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                for call in msg.tool_calls:
                    parts.append(types.Part.from_function_call(name=call.name, args=call.args))
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                parts = []
                for res in msg.tool_results:
                    parts.append(types.Part.from_function_response(name=res.name, response={"result": res.output}))
                contents.append(types.Content(role="user", parts=parts))

        # Format Tool Declarations
        config_tools = None
        if tools:
            decls = []
            for t in tools:
                if isinstance(t, dict) and "name" in t:
                    decls.append(t)
                elif isinstance(t, dict) and "function_declarations" in t:
                    decls.extend(t["function_declarations"])
            if decls:
                config_tools = [types.Tool(function_declarations=decls)]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=config_tools,
            temperature=0.2,
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        # Parse Gemini response into unified LLMResponse
        tool_calls = []
        response_text = ""
        try:
            if response.text:
                response_text = response.text
        except Exception:
            response_text = ""

        # Extract function calls if present
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                fn_call = getattr(part, "function_call", None)
                if fn_call:
                    name = getattr(fn_call, "name", None) or ""
                    args = getattr(fn_call, "args", {}) or {}
                    if not isinstance(args, dict):
                        args = dict(args)
                    tool_calls.append(ToolCall(name=name, args=args))

        # Token usage
        prompt_tokens = 0
        comp_tokens = 0
        total_tokens = 0
        if getattr(response, "usage_metadata", None):
            meta = response.usage_metadata
            prompt_tokens = getattr(meta, "prompt_token_count", 0) or 0
            comp_tokens = getattr(meta, "candidates_token_count", 0) or 0
            total_tokens = getattr(meta, "total_token_count", 0) or (prompt_tokens + comp_tokens)

        return LLMResponse(
            text=response_text if response_text else None,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                total_tokens=total_tokens,
            ),
            raw_response=response,
        )


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """
    Adapter for OpenAI-compatible endpoints (OpenAI, Ollama, vLLM, DeepSeek, LocalAI).
    Uses standard library urllib.request to avoid mandatory external dependencies.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        name: str = "OpenAICompatibleAdapter",
    ):
        super().__init__(model_name=model_name, name=name)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        endpoint = f"{self.base_url}/chat/completions"

        formatted_messages = []
        if system_instruction:
            formatted_messages.append({"role": "system", "content": system_instruction})

        for msg in messages:
            if msg.role == "user":
                formatted_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                m: dict[str, Any] = {"role": "assistant"}
                if msg.content:
                    m["content"] = msg.content
                if msg.tool_calls:
                    m["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                        }
                        for tc in msg.tool_calls
                    ]
                formatted_messages.append(m)
            elif msg.role == "tool":
                for tr in msg.tool_results:
                    formatted_messages.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_call_id or "call_unknown",
                        "name": tr.name,
                        "content": tr.output,
                    })

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": 0.2,
        }

        if tools:
            tool_schemas = []
            for t in tools:
                if isinstance(t, dict) and "name" in t:
                    tool_schemas.append({"type": "function", "function": t})
                elif isinstance(t, dict) and "function_declarations" in t:
                    for d in t["function_declarations"]:
                        tool_schemas.append({"type": "function", "function": d})
            if tool_schemas:
                payload["tools"] = tool_schemas

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAICompatible API error ({e.code}): {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with OpenAI-compatible endpoint: {e}")

        choice = res_body.get("choices", [{}])[0]
        msg_obj = choice.get("message", {})
        text = msg_obj.get("content")

        tool_calls = []
        for raw_tc in msg_obj.get("tool_calls", []):
            fn = raw_tc.get("function", {})
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {"raw": raw_args}
            tool_calls.append(ToolCall(name=fn_name, args=args, id=raw_tc.get("id", "")))

        usage_data = res_body.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        comp_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + comp_tokens)

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                total_tokens=total_tokens,
            ),
            raw_response=res_body,
        )
