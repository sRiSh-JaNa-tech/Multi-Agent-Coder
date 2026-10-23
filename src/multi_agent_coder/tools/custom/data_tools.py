"""
Built-in versatile utility tools for general-purpose tasks, CTFs, data processing, and web probing.
Demonstrates the plug-and-play @tool decorator.
"""

import base64
import codecs
from typing import Any
import urllib.parse
import urllib.request

from multi_agent_coder.tools.decorator import tool
from multi_agent_coder.security.permissions import AgentCapability


@tool(
    name="http_request",
    description="Send an HTTP GET, POST, or other request to a URL and inspect the status and response body.",
    required_capability=AgentCapability.EXECUTE_TESTS,
)
def http_request(
    url: str,
    method: str = "GET",
    data: str = "",
    headers_json: str = "{}",
    timeout: int = 15,
) -> str:
    """Send an HTTP request and return status code, headers, and body preview."""
    import json
    try:
        req_headers = {"User-Agent": "MultiAgentCoder/1.0"}
        if headers_json and headers_json != "{}":
            try:
                custom_h = json.loads(headers_json)
                if isinstance(custom_h, dict):
                    req_headers.update(custom_h)
            except Exception:
                pass

        data_bytes = data.encode("utf-8") if data and method.upper() in ("POST", "PUT", "PATCH") else None
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            return f"Status: {status}\nHeaders: {dict(resp.headers)}\n\nResponse Body:\n{body[:16000]}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return f"HTTPError {e.code}: {e.reason}\nResponse Body:\n{err_body[:2000]}"
    except Exception as e:
        return f"Request Error: {e}"


@tool(
    name="decode_payload",
    description="Decode common encodings: 'base64', 'hex', 'url', 'rot13', 'binary', or 'auto'. Essential for CTF and data decoding.",
    required_capability=AgentCapability.READ_ONLY,
)
def decode_payload(payload: str, encoding: str = "auto") -> str:
    """Decode string payload according to specified encoding."""
    enc = encoding.lower().strip()
    text = payload.strip()
    results = []

    if enc in ("auto", "base64"):
        try:
            # Handle base64
            padded = text + "=" * ((4 - len(text) % 4) % 4)
            b64_out = base64.b64decode(padded).decode("utf-8", errors="replace")
            results.append(f"[base64]: {b64_out}")
        except Exception:
            if enc == "base64":
                results.append("[base64]: Failed to decode")

    if enc in ("auto", "hex"):
        try:
            cleaned_hex = text.replace("0x", "").replace(" ", "").replace(":", "")
            hex_out = bytes.fromhex(cleaned_hex).decode("utf-8", errors="replace")
            results.append(f"[hex]: {hex_out}")
        except Exception:
            if enc == "hex":
                results.append("[hex]: Failed to decode")

    if enc in ("auto", "url"):
        try:
            url_out = urllib.parse.unquote(text)
            if url_out != text or enc == "url":
                results.append(f"[url]: {url_out}")
        except Exception:
            pass

    if enc in ("auto", "rot13"):
        try:
            rot_out = codecs.decode(text, "rot_13")
            results.append(f"[rot13]: {rot_out}")
        except Exception:
            pass

    if not results:
        return f"Could not decode payload with encoding '{encoding}'."
    return "\n".join(results)
