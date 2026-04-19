"""Claude Code-style full-screen interactive TUI for Engram."""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import urllib.parse
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.layout.screen import Point
from prompt_toolkit.styles import Style

_VERSION = "0.1.1"

_STYLE = Style.from_dict(
    {
        "header.title": "bold noinherit #ffffff",
        "header.version": "noinherit #555555",
        "header.mode": "bold noinherit #00dd55",
        "header.id": "noinherit #555555",
        "header.cwd": "noinherit #555555",
        "header.tagline": "noinherit #ff8800",
        "header.logo": "bold noinherit #00dd55",
        "separator": "noinherit #333333",
        "prompt": "bold noinherit #00dd55",
        "output": "noinherit #cccccc",
        "output.cmd": "bold noinherit #00dd55",
        "output.error": "noinherit #ff5555",
        "output.dim": "noinherit #555555",
        "output.warn": "noinherit #ffaa00",
        "output.label": "bold noinherit #00dd55",
        "toolbar": "noinherit bg:#111111 #444444",
        "toolbar.key": "noinherit bg:#111111 #00dd55",
        "toolbar.sep": "noinherit bg:#111111 #333333",
    }
)

_VALID_COMMANDS = {
    "conflicts",
    "resolve",
    "search",
    "status",
    "whoami",
    "export",
    "info",
    "stats",
    "verify",
    "doctor",
}

_HELP_LINES: list[tuple[str, str]] = [
    ("class:output.dim", "\n"),
    ("class:output", "  Commands:\n"),
    ("class:output", "    conflicts                           — refresh conflict list\n"),
    ("class:output", "    resolve <id> keep_a|keep_b|dismiss  — resolve a conflict\n"),
    ("class:output", "    clear                               — clear output  (Ctrl+L)\n"),
    ("class:output", "    quit / q                            — exit          (Ctrl+C)\n"),
    ("class:output.dim", "\n"),
    ("class:output.dim", "  Conflicts are shared with the web dashboard in real time.\n"),
    ("class:output.dim", "\n"),
]

# Default local server address — matches `engram serve --http`
_LOCAL_SERVER = "http://localhost:7474"


# ── server API helpers ────────────────────────────────────────────────


def _http_get(url: str, timeout: int = 5) -> Any | None:
    """GET url, return parsed JSON or None on any error."""
    try:
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(
            parsed.hostname or "localhost", parsed.port or 80, timeout=timeout
        )
        conn.request("GET", parsed.path + (f"?{parsed.query}" if parsed.query else ""))
        resp = conn.getresponse()
        if resp.status == 200:
            return json.loads(resp.read())
    except Exception:
        pass
    return None


def _http_post(url: str, body: dict[str, Any], timeout: int = 5) -> tuple[int, Any]:
    """POST JSON body to url, return (status_code, parsed_json)."""
    try:
        parsed = urllib.parse.urlparse(url)
        raw = json.dumps(body).encode()
        conn = http.client.HTTPConnection(
            parsed.hostname or "localhost", parsed.port or 80, timeout=timeout
        )
        conn.request(
            "POST",
            parsed.path,
            raw,
            {"Content-Type": "application/json", "Content-Length": str(len(raw))},
        )
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    except Exception as exc:
        return 0, {"error": str(exc)}


def _server_url(ws: Any) -> str:
    """Return the server base URL to use for API calls."""
    if ws and ws.server_url:
        return ws.server_url.rstrip("/")
    return _LOCAL_SERVER


# ── conflict display helpers ──────────────────────────────────────────

_SEV_COLOURS = {"high": "class:output.error", "medium": "class:output.warn", "low": "class:output"}


def _format_conflicts(conflicts: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Render a numbered conflict list for the TUI output area."""
    lines: list[tuple[str, str]] = []
    if not conflicts:
        lines.append(("class:output.dim", "  ✓ No open conflicts — agents are aligned.\n"))
        return lines

    lines.append(
        ("class:output", f"  {len(conflicts)} open conflict(s) — shared with dashboard:\n\n")
    )
    for i, c in enumerate(conflicts, 1):
        cid = (c.get("conflict_id") or c.get("id") or "")[:16]
        short = cid[:8]
        explanation = c.get("explanation") or "Conflicting information detected"
        severity = c.get("severity", "medium")
        sev_style = _SEV_COLOURS.get(severity, "class:output")

        # Normalise nested vs flat fact shapes
        fa = c.get("fact_a") or {}
        fb = c.get("fact_b") or {}
        fa_content = (fa.get("content") or c.get("fact_a_content") or "")[:90]
        fb_content = (fb.get("content") or c.get("fact_b_content") or "")[:90]
        fa_scope = fa.get("scope") or c.get("fact_a_scope") or ""
        fb_scope = fb.get("scope") or c.get("fact_b_scope") or ""

        lines.append(("class:output.label", f"  [{i}] "))
        lines.append((sev_style, f"[{severity}] "))
        lines.append(("class:output.dim", f"id:{short}\n"))
        lines.append(("class:output", f"      {explanation}\n"))
        if fa_content:
            scope_tag = f" ({fa_scope})" if fa_scope else ""
            lines.append(("class:output.dim", f"      A{scope_tag}: {fa_content}\n"))
        if fb_content:
            scope_tag = f" ({fb_scope})" if fb_scope else ""
            lines.append(("class:output.dim", f"      B{scope_tag}: {fb_content}\n"))
        lines.append(("class:output.dim", f"      resolve {short} keep_a|keep_b|dismiss\n\n"))

    lines.append(("class:output.dim", "  Changes sync instantly with the web dashboard.\n"))
    return lines


# ── conflict fetch / resolve via server ───────────────────────────────


def _load_conflicts(ws: Any, output_lines: list[tuple[str, str]]) -> None:
    """Fetch open conflicts from the server and append formatted output."""
    base = _server_url(ws)
    data = _http_get(f"{base}/api/conflicts?status=open")

    if data is None:
        # Server not running — fall back to CLI subprocess
        output_lines.append(("class:output.dim", "  (server offline — using local engine)\n"))
        _run_engram_command("conflicts", "", output_lines)
        return

    output_lines.extend(_format_conflicts(data if isinstance(data, list) else []))


def _resolve_conflict(
    ws: Any,
    conflict_id: str,
    resolution_type: str,
    output_lines: list[tuple[str, str]],
) -> None:
    """Resolve a conflict via the server API and report the result."""
    base = _server_url(ws)

    # Map short aliases to canonical resolution types
    _aliases = {
        "keep_a": "winner",
        "keep_b": "winner",
        "dismiss": "dismissed",
        "dismissed": "dismissed",
        "winner": "winner",
        "merge": "merge",
    }
    resolution_type_norm = _aliases.get(resolution_type.lower(), resolution_type.lower())
    if resolution_type_norm not in ("winner", "merge", "dismissed"):
        output_lines.append(
            (
                "class:output.error",
                f"  Unknown resolution '{resolution_type}'. Use keep_a, keep_b, or dismiss.\n",
            )
        )
        return

    # For keep_a/keep_b we need the actual fact IDs — fetch the conflict first
    winning_claim_id: str | None = None
    if resolution_type.lower() in ("keep_a", "keep_b"):
        data = _http_get(f"{base}/api/conflicts?status=open")
        if isinstance(data, list):
            for c in data:
                cid = c.get("conflict_id") or c.get("id") or ""
                if cid.startswith(conflict_id):
                    if resolution_type.lower() == "keep_a":
                        fa = c.get("fact_a") or {}
                        winning_claim_id = fa.get("fact_id") or fa.get("id") or c.get("fact_a_id")
                    else:
                        fb = c.get("fact_b") or {}
                        winning_claim_id = fb.get("fact_id") or fb.get("id") or c.get("fact_b_id")
                    conflict_id = cid  # use full ID for the resolve call
                    break

    note = f"Resolved via TUI ({resolution_type})"
    payload: dict[str, Any] = {
        "conflict_id": conflict_id,
        "resolution_type": resolution_type_norm,
        "resolution": note,
    }
    if winning_claim_id:
        payload["winning_claim_id"] = winning_claim_id

    status, result = _http_post(f"{base}/api/resolve", payload)

    if status == 0:
        # Server offline — fall back to CLI
        output_lines.append(("class:output.dim", "  (server offline — using local engine)\n"))
        _run_engram_command("resolve", f"{conflict_id} {resolution_type_norm} {note}", output_lines)
        return

    if status != 200:
        err = result.get("error") or result.get("detail") or f"HTTP {status}"
        output_lines.append(("class:output.error", f"  Resolve failed: {err}\n"))
        return

    output_lines.append(
        ("class:output.label", f"  ✓ Conflict {conflict_id[:8]} resolved ({resolution_type}).\n")
    )
    output_lines.append(("class:output.dim", "  Dashboard will reflect this immediately.\n"))


def run_tui(ws: Any, ctx: Any) -> None:
    """Launch the Claude Code-style interactive shell."""
    if ws.server_url and not ws.db_url:
        mode_label = "hosted"
    elif ws.db_url:
        mode_label = "team · PostgreSQL"
    else:
        mode_label = "local · SQLite"

    workspace_id = ws.engram_id or "-"
    try:
        rel = os.path.relpath(os.getcwd(), os.path.expanduser("~"))
        cwd = "~/" + rel if not rel.startswith("..") else os.getcwd()
    except ValueError:
        cwd = os.getcwd()

    # Mutable state
    state: dict[str, Any] = {}
    output_lines: list[tuple[str, str]] = []

    # ── formatted text producers ──────────────────────────────────────────

    _LOGO_OPEN = [
        "  ▄████▄  ",
        " ██▄██▄██ ",
        " ███▀▀███ ",
        " ▀ ▀  ▀ ▀ ",
    ]
    _LOGO_CLOSED = [
        "  ▄████▄  ",
        " ████████ ",
        " ███▀▀███ ",
        " ▀ ▀  ▀ ▀ ",
    ]

    def header_text() -> AnyFormattedText:
        logo = _LOGO_OPEN if state.get("eyes", "open") == "open" else _LOGO_CLOSED
        lines = [
            [
                ("class:header.logo", logo[0]),
                ("class:header.title", "   Engram "),
                ("class:header.version", f"v{_VERSION}"),
            ],
            [
                ("class:header.logo", logo[1]),
                ("class:header.mode", f"   {mode_label} "),
                ("class:header.id", f"· {workspace_id}"),
            ],
            [("class:header.logo", logo[2]), ("class:header.cwd", f"   {cwd}")],
            [
                ("class:header.logo", logo[3]),
                ("class:header.tagline", "   Shared memory for AI agents"),
            ],
        ]

        result: list[tuple[str, str]] = []
        for line in lines:
            result.extend(line)
            result.append(("", "\n"))
        return result

    def separator_text() -> AnyFormattedText:
        return [("class:separator", "─" * 200)]

    def output_text() -> AnyFormattedText:
        return list(output_lines)

    def output_cursor_pos() -> Point:
        total = sum(t.count("\n") for _, t in output_lines)
        return Point(x=0, y=max(0, total - 1))

    def toolbar_text() -> AnyFormattedText:
        return [
            ("class:toolbar", "  "),
            ("class:toolbar.key", "conflicts"),
            ("class:toolbar", " refresh"),
            ("class:toolbar.sep", "   ·   "),
            ("class:toolbar.key", "resolve <id> keep_a|keep_b|dismiss"),
            ("class:toolbar.sep", "   ·   "),
            ("class:toolbar.key", "?"),
            ("class:toolbar", " help"),
            ("class:toolbar.sep", "   ·   "),
            ("class:toolbar.key", "Ctrl+C"),
            ("class:toolbar", " quit"),
            ("class:toolbar", "  "),
        ]

    # ── input & key handling ──────────────────────────────────────────────

    input_buf = Buffer(name="main_input", multiline=False)

    def run_cmd(cmd: str, arg: str, app: Application) -> None:
        output_lines.append(("class:output.cmd", f"\n  > {cmd}{' ' + arg if arg else ''}\n"))
        _run_engram_command(cmd, arg, output_lines)
        app.invalidate()

    def handle_command(text: str, app: Application) -> None:
        text = text.strip()
        if not text:
            return

        output_lines.append(("class:output.cmd", f"\n  > {text}\n"))
        parts = text.split(None, 2)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        extra = parts[2] if len(parts) > 2 else ""

        if cmd in ("quit", "exit", "q"):
            app.exit()
            return
        if cmd in ("?", "help"):
            output_lines.extend(_HELP_LINES)
            return
        if cmd == "clear":
            output_lines.clear()
            return
        if cmd not in _VALID_COMMANDS:
            output_lines.append(
                ("class:output.error", f"  Unknown command: {cmd}. Type ? for help.\n")
            )
            return

        if cmd == "conflicts":
            _load_conflicts(ws, output_lines)
        elif cmd == "resolve":
            if not arg:
                output_lines.append(
                    ("class:output.error", "  Usage: resolve <id> keep_a|keep_b|dismiss\n")
                )
            else:
                resolution = extra or "dismissed"
                _resolve_conflict(ws, arg, resolution, output_lines)
                # Auto-refresh conflicts after resolving
                output_lines.append(("class:output.dim", "\n"))
                _load_conflicts(ws, output_lines)
        elif cmd == "search" and not arg:
            output_lines.append(("class:output.error", "  Usage: search <query>\n"))
        else:
            _run_engram_command(cmd, arg + (" " + extra if extra else ""), output_lines)

        app.invalidate()

    kb = KeyBindings()

    @kb.add("enter")
    def _enter(event: Any) -> None:
        text = input_buf.text
        input_buf.reset()
        handle_command(text, event.app)

    @kb.add("c-c")
    @kb.add("c-d")
    def _exit(event: Any) -> None:
        event.app.exit()

    @kb.add("c-l")
    def _clear(event: Any) -> None:
        output_lines.clear()
        event.app.invalidate()

    @kb.add("c-r")
    def _refresh(event: Any) -> None:
        output_lines.append(("class:output.cmd", "\n  > conflicts\n"))
        _load_conflicts(ws, output_lines)
        event.app.invalidate()

    # ── layout ────────────────────────────────────────────────────────────
    #
    # Order (top → bottom):
    #   Header      (fixed 4 lines)
    #   Separator   (fixed 1 line)
    #   Output area (flexible — conflicts on startup, fills with output)
    #   Separator   (fixed 1 line)
    #   Input bar   (fixed 1 line)
    #   Toolbar     (fixed 1 line)

    layout = Layout(
        HSplit(
            [
                Window(
                    FormattedTextControl(header_text, focusable=False),
                    height=D.exact(4),
                    dont_extend_height=True,
                ),
                Window(
                    FormattedTextControl(separator_text, focusable=False),
                    height=D.exact(1),
                    dont_extend_height=True,
                ),
                Window(
                    FormattedTextControl(
                        output_text,
                        get_cursor_position=output_cursor_pos,
                        focusable=False,
                    ),
                    wrap_lines=True,
                    dont_extend_height=True,
                ),
                Window(
                    FormattedTextControl(separator_text, focusable=False),
                    height=D.exact(1),
                    dont_extend_height=True,
                ),
                Window(
                    BufferControl(
                        buffer=input_buf,
                        input_processors=[BeforeInput("> ", style="class:prompt")],
                    ),
                    height=D.exact(1),
                    dont_extend_height=True,
                ),
                Window(),  # pushes output and input to top, toolbar to bottom
                Window(
                    FormattedTextControl(toolbar_text, focusable=False),
                    height=D.exact(1),
                    dont_extend_height=True,
                    style="class:toolbar",
                ),
            ]
        ),
        focused_element=input_buf,
    )

    app = Application(
        layout=layout,
        style=_STYLE,
        key_bindings=kb,
        full_screen=True,
        cursor=CursorShape.BLINKING_BLOCK,
        mouse_support=False,
    )

    import threading
    import time

    def _blink() -> None:
        while True:
            time.sleep(3)
            state["eyes"] = "closed"
            app.invalidate()
            time.sleep(0.15)
            state["eyes"] = "open"
            app.invalidate()

    threading.Thread(target=_blink, daemon=True).start()

    # Load conflicts immediately on startup
    _load_conflicts(ws, output_lines)

    app.run()


# ── command runner ─────────────────────────────────────────────────────


def _run_engram_command(cmd: str, arg: str, output_lines: list[tuple[str, str]]) -> None:
    engram_bin = _find_engram_bin()
    cli_args = [engram_bin, cmd]
    if arg:
        cli_args.extend(arg.split())

    try:
        result = subprocess.run(cli_args, capture_output=True, text=True, timeout=30)
        combined = (result.stdout + result.stderr).strip()
        if combined in ("[]", "{}", ""):
            output_lines.append(("class:output.dim", f"  No {cmd} found.\n"))
        elif combined:
            err = result.returncode != 0
            for line in combined.splitlines():
                style = "class:output.error" if err else "class:output"
                output_lines.append((style, f"  {line}\n"))
        else:
            output_lines.append(("class:output.dim", f"  No output from {cmd}.\n"))
    except subprocess.TimeoutExpired:
        output_lines.append(("class:output.error", "  Command timed out after 30s\n"))
    except FileNotFoundError:
        output_lines.append(("class:output.error", f"  Could not find: {engram_bin}\n"))
    except Exception as e:
        output_lines.append(("class:output.error", f"  Error: {e}\n"))


def _find_engram_bin() -> str:
    argv0 = sys.argv[0]
    if os.path.isfile(argv0) and os.access(argv0, os.X_OK):
        return argv0
    return "engram"
