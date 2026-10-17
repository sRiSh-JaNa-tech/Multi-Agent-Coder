"""
Authentication & Gemini API Key Validation Module.

Handles loading, validating (via live connection test prompt), prompting, and
persisting GEMINI_API_KEY across all workspace environments.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

try:
    from common.logging_config import setup_logging
except ImportError:
    try:
        from .logging_config import setup_logging
    except ImportError:
        from multi_agent_coder.common.logging_config import setup_logging

logger = setup_logging(__name__)

# In-memory cache of keys that have already passed connection validation in this process
_VALIDATED_KEYS: Set[str] = set()


def get_known_env_files() -> List[Path]:
    """Return all plausible .env file locations across the workspaces."""
    candidates = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(r"C:\Users\srish\Desktop\Multi-Coding-Agent\.env"),
        Path(r"C:\Users\srish\Desktop\Multi-Coding-Agent\codebase-navigator\.env"),
        Path(r"C:\Users\srish\Desktop\Hello_world\Gemini-Agentic-AI\.env"),
        Path(r"C:\Users\srish\Desktop\Hello_world\Gemini-Agentic-AI\codebase-navigator\.env"),
    ]
    unique: List[Path] = []
    seen: Set[str] = set()
    for p in candidates:
        try:
            resolved = str(p.resolve())
            if resolved not in seen:
                seen.add(resolved)
                unique.append(p)
        except Exception:
            if str(p) not in seen:
                seen.add(str(p))
                unique.append(p)
    return unique


def find_configured_api_key() -> str:
    """Find a configured Gemini API key from environment variables or .env files."""
    # 1. Check active environment variables
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.getenv(env_var, "").strip().strip('"').strip("'")
        if val:
            return val

    # 2. Check all known .env files directly
    for env_path in get_known_env_files():
        if env_path.exists() and env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    for prefix in ("GEMINI_API_KEY=", "GOOGLE_API_KEY="):
                        if line.startswith(prefix):
                            candidate = line[len(prefix):].strip().strip('"').strip("'")
                            if candidate:
                                os.environ["GEMINI_API_KEY"] = candidate
                                return candidate
            except Exception:
                pass

    return ""


def persist_api_key(api_key: str) -> None:
    """Save the validated API key across all known .env files."""
    api_key = api_key.strip().strip('"').strip("'")
    if not api_key:
        return

    os.environ["GEMINI_API_KEY"] = api_key

    for env_path in get_known_env_files():
        try:
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()
                new_lines = [
                    l for l in lines
                    if not (l.strip().startswith("GEMINI_API_KEY=") or l.strip().startswith("GOOGLE_API_KEY="))
                ]
                new_lines.append(f"GEMINI_API_KEY={api_key}")
                env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            else:
                if env_path.parent.exists():
                    env_path.write_text(f"GEMINI_API_KEY={api_key}\n", encoding="utf-8")
        except Exception:
            pass


def validate_gemini_api_key(
    api_key: str,
    model: str = "gemini-2.5-flash-lite",
    bypass_cache: bool = False,
) -> Tuple[bool, str]:
    """Validate that the Gemini API key connects successfully using a minimal prompt.

    Returns:
        (True, "OK message") if verification succeeds.
        (False, "Error message") if verification fails.
    """
    key = api_key.strip().strip('"').strip("'")
    if not key:
        return False, "API key cannot be empty."



    if not bypass_cache and key in _VALIDATED_KEYS:
        return True, "API key verified (cached)."

    try:
        client = genai.Client(api_key=key)
        # Send minimal 1-token test prompt to verify authentication and connectivity
        response = client.models.generate_content(
            model=model,
            contents="ping",
            config=types.GenerateContentConfig(
                max_output_tokens=2,
                temperature=0.0,
            ),
        )
        if response and response.text is not None:
            _VALIDATED_KEYS.add(key)
            return True, "API connection verified successfully."
        _VALIDATED_KEYS.add(key)
        return True, "API connection verified."
    except Exception as exc:
        err_msg = str(exc)
        if "API_KEY_INVALID" in err_msg or "API key not valid" in err_msg:
            return False, "Google API error: 400 API_KEY_INVALID. The provided key is not recognized by Google AI Studio."
        if "UNAUTHENTICATED" in err_msg or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in err_msg:
            return False, "Google API error: 401 UNAUTHENTICATED. The credential was rejected by Google's gateway."
        if "PERMISSION_DENIED" in err_msg:
            return False, f"Google API error: Permission Denied. ({err_msg})"
        return False, f"Connection failed: {err_msg}"


def ensure_api_key(
    console: Optional[Console] = None,
    force_prompt: bool = False,
    model: str = "gemini-2.5-flash-lite",
) -> str:
    """Ensure a valid, working GEMINI_API_KEY is available.

    1. Checks if a key is already present in environment or .env files.
    2. If present and not force_prompt, validates it with a lightweight test prompt.
       - If valid: proceeds immediately without asking.
       - If invalid: notifies user with the exact error and prompts for a valid key.
    3. When prompting, immediately validates the entered key via test prompt before saving.
    """
    _console = console or Console()

    if not force_prompt:
        existing_key = find_configured_api_key()
        if existing_key:
            _console.print("[dim cyan]Validating Gemini API key connection...[/dim cyan]")
            is_valid, err_msg = validate_gemini_api_key(existing_key, model=model)
            if is_valid:
                _console.print("[bold green][OK] Gemini API key validated successfully. Connected to Google Gemini.[/bold green]\n")
                return existing_key
            else:
                _console.print(
                    Panel(
                        f"[bold red]Configured GEMINI_API_KEY failed connection validation:[/bold red]\n\n"
                        f"{err_msg}\n\n"
                        "Please enter a valid working Google Gemini API key to proceed.\n"
                        "You can generate one for free at: [cyan]https://aistudio.google.com/app/apikey[/cyan]",
                        title="API Key Connection Failed",
                        border_style="red",
                    )
                )
        else:
            _console.print(
                Panel(
                    "[bold yellow]GEMINI_API_KEY not found in environment or .env[/bold yellow]\n\n"
                    "Please enter your Google Gemini API key to proceed.\n"
                    "You can generate one for free at: [cyan]https://aistudio.google.com/app/apikey[/cyan]\n"
                    "[dim](Google AI Studio keys typically start with 'AQ.' or 'AIzaSy')[/dim]",
                    title="Gemini API Key Required",
                    border_style="yellow",
                )
            )
    else:
        _console.print(
            Panel(
                "[bold yellow]Gemini API Authentication Re-prompt[/bold yellow]\n\n"
                "The previous API request was rejected by Google.\n"
                "Please enter a valid Google Gemini API key to proceed.\n"
                "Generate one for free at: [cyan]https://aistudio.google.com/app/apikey[/cyan]",
                title="Gemini API Key Required",
                border_style="yellow",
            )
        )

    # Prompt loop with validation check
    while True:
        try:
            if sys.stdin.isatty():
                entered_key = Prompt.ask("[bold green]Enter your GEMINI_API_KEY[/bold green]", password=True).strip()
            else:
                _console.print("[bold green]Enter your GEMINI_API_KEY:[/bold green] ", end="")
                entered_key = sys.stdin.readline().strip()

            entered_key = entered_key.strip('"').strip("'")
            if not entered_key:
                _console.print("[red]API key cannot be empty. Please enter a valid key.[/red]")
                continue

            _console.print("[dim cyan]Validating key with Google Gemini...[/dim cyan]")
            is_valid, err_msg = validate_gemini_api_key(entered_key, model=model, bypass_cache=True)
            if is_valid:
                _console.print("[bold green][OK] Connection successful! API key verified and saved.[/bold green]\n")
                persist_api_key(entered_key)
                return entered_key
            else:
                _console.print(f"[bold red][FAIL] Connection test failed:[/bold red] {err_msg}")
                _console.print("[yellow]Please check the key and try again, or obtain a new key at https://aistudio.google.com/app/apikey[/yellow]\n")

        except (KeyboardInterrupt, EOFError):
            _console.print("\n[yellow]Exiting: API key entry cancelled.[/yellow]")
            raise SystemExit(0)
