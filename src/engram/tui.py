"""Claude Code-style full-screen interactive TUI for Engram."""

from __future__ import annotations

import os
import subprocess
import sys
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
        "header.title": "bold #ffffff",
        "header.version": "#555555",
        "header.mode": "bold #00dd55",
        "header.id": "#555555",
        "header.cwd": "#555555",
        "header.tagline": "#ff8800",
        "separator": "#333333",
        "prompt": "bold #00dd55",
        "output": "#cccccc",
        "output.cmd": "bold #00dd55",
        "output.error": "#ff4444",
        "output.dim": "#555555",
        "toolbar": "bg:#111111 #444444",
        "toolbar.key": "bg:#111111 #00dd55",
        "toolbar.sep": "bg:#111111 #333333",
    }
)

# Commands that the TUI passes through to the engram binary
_VALID_COMMANDS = {
    "conflicts",
    "search",
    "status",
    "whoami",
    "info",
    "tail",
    "export",
    "stats",
    "verify",
    "doctor",
}

_HELP_LINES: list[tuple[str, str]] = [
    ("class:output.dim", "\n"),
    ("class:output", "  Available commands:\n"),
    ("class:output", "    conflicts   — review open memory conflicts\n"),
    ("class:output", "    search <q>  — query workspace memory\n"),
    ("class:output", "    status      — workspace info\n"),
    ("class:output", "    whoami      — show identity\n"),
    ("class:output", "    tail        — stream live facts\n"),
    ("class:output", "    export      — export workspace data\n"),
    ("class:output", "    clear       — clear this output  (Ctrl+L)\n"),
    ("class:output", "    quit / q    — exit               (Ctrl+C)\n"),
    ("class:output.dim", "\n"),
]


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

    output_lines: list[tuple[str, str]] = [
        ("class:output.dim", "\n"),
        ("class:output", "  Type a command or ? for help.\n"),
        ("class:output.dim", "\n"),
    ]

    # ── formatted text producers ─────────────────────────────────────────

    def header_text() -> AnyFormattedText:
        return [
            ("class:header.title", "  Engram"),
            ("class:header.version", f"  v{_VERSION}"),
            ("", "\n"),
            ("class:header.mode", f"  {mode_label}"),
            ("class:header.id", f"  ·  {workspace_id}"),
            ("class:header.cwd", f"  ·  {cwd}"),
            ("", "\n"),
            ("class:header.tagline", "  Shared memory for engineering teams"),
            ("", "\n"),
        ]

    def separator_text() -> AnyFormattedText:
        return [("class:separator", "─" * 200)]

    def output_text() -> AnyFormattedText:
        return list(output_lines)

    def output_cursor_pos() -> Point:
        """Always position cursor at end of output so the window auto-scrolls."""
        total_lines = sum(t.count("\n") for _, t in output_lines)
        return Point(x=0, y=max(0, total_lines - 1))

    def toolbar_text() -> AnyFormattedText:
        return [
            ("class:toolbar.key", "  ?"),
            ("class:toolbar", " help"),
            ("class:toolbar.sep", "   ·   "),
            ("class:toolbar", "conflicts"),
            ("class:toolbar.sep", "  ·  "),
            ("class:toolbar", "search <q>"),
            ("class:toolbar.sep", "  ·  "),
            ("class:toolbar", "status"),
            ("class:toolbar.sep", "  ·  "),
            ("class:toolbar", "quit"),
            ("class:toolbar", "  "),
        ]

    # ── input handling ────────────────────────────────────────────────────

    input_buf = Buffer(name="main_input", multiline=False)

    def handle_command(text: str, app: Application) -> None:
        text = text.strip()
        if not text:
            return

        output_lines.append(("class:output.cmd", f"\n  > {text}\n"))

        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

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

        _run_engram_command(cmd, arg, output_lines)

    kb = KeyBindings()

    @kb.add("enter")
    def _on_enter(event: Any) -> None:
        text = input_buf.text
        input_buf.reset()
        handle_command(text, event.app)

    @kb.add("c-c")
    @kb.add("c-d")
    def _on_exit(event: Any) -> None:
        event.app.exit()

    @kb.add("c-l")
    def _on_clear(event: Any) -> None:
        output_lines.clear()
        event.app.invalidate()

    # ── layout ───────────────────────────────────────────────────────────

    output_control = FormattedTextControl(
        output_text,
        get_cursor_position=output_cursor_pos,
        focusable=False,
    )

    layout = Layout(
        HSplit(
            [
                Window(
                    FormattedTextControl(header_text, focusable=False),
                    height=D.exact(3),
                    dont_extend_height=True,
                ),
                Window(
                    FormattedTextControl(separator_text, focusable=False),
                    height=D.exact(1),
                    dont_extend_height=True,
                ),
                Window(
                    output_control,
                    wrap_lines=True,
                    dont_extend_width=False,
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
        color_depth=None,
    )

    app.run()


# ── command runner ────────────────────────────────────────────────────


def _run_engram_command(cmd: str, arg: str, output_lines: list[tuple[str, str]]) -> None:
    """Run an engram subcommand via subprocess and append output."""
    engram_bin = _find_engram_bin()
    cli_args = [engram_bin, cmd]
    if arg:
        cli_args.extend(arg.split())

    try:
        result = subprocess.run(
            cli_args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = (result.stdout + result.stderr).strip()
        if combined:
            for line in combined.splitlines():
                style = "class:output.error" if result.returncode != 0 else "class:output"
                output_lines.append((style, f"  {line}\n"))
        else:
            output_lines.append(("class:output.dim", "  (no output)\n"))
    except subprocess.TimeoutExpired:
        output_lines.append(("class:output.error", "  Command timed out after 30s\n"))
    except FileNotFoundError:
        output_lines.append(
            ("class:output.error", f"  Could not find engram binary: {engram_bin}\n")
        )
    except Exception as e:
        output_lines.append(("class:output.error", f"  Error: {e}\n"))


def _find_engram_bin() -> str:
    """Return the path to the engram binary."""
    argv0 = sys.argv[0]
    if os.path.isfile(argv0) and os.access(argv0, os.X_OK):
        return argv0
    return "engram"
