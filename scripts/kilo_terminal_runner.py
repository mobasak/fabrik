#!/usr/bin/env python3
"""
Kilo Terminal Runner - Rich TUI for Kilo CLI agent wrappers.

Replaces tee-based streaming with a full-screen Textual UI while preserving
the raw output file format for Traycer report extraction.

Usage:
    python kilo_terminal_runner.py --output /tmp/output.txt -- kilo run ...

Fallback:
    If Textual import fails or terminal too small, falls back to plain mode.
"""

from __future__ import annotations

import argparse
import codecs
import sys
import time
from enum import Enum, auto
from pathlib import Path

# =============================================================================
# STREAMING SANITIZER (Stateful State Machine)
# =============================================================================


class State(Enum):
    """State machine states for control sequence parsing."""

    NORMAL = auto()
    ESC = auto()
    CSI = auto()
    OSC = auto()
    OSC_ESC = auto()
    ESC_PAREN = auto()
    ESC_HASH = auto()


class StreamingSanitizer:
    """
    Stateful streaming sanitizer for terminal output.

    Strips control sequences expected from Kilo/common CLI output.
    State persists across chunk and line boundaries.

    Handles:
    - CSI: ESC [ <params> <final-byte>
    - OSC: ESC ] <text> BEL or ESC ] <text> ESC \\
    - Character set: ESC ( <char>, ESC ) <char>
    - DEC screen: ESC # <digit>
    - Single-char: ESC 7, ESC 8, ESC =, ESC >
    - Carriage returns (line rewrites for progress bars)
    - CR+LF line endings (PTY standard)
    - Backspace
    """

    ESC_SINGLE = set("78=>")
    ESC_PREFIX_PAREN = set("()")
    ESC_PREFIX_HASH = set("#")

    def __init__(self):
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.state = State.NORMAL
        self.line_buffer: list[str] = []
        self.output_lines: list[str] = []
        self.pending_cr = False  # Track pending CR for CR+LF handling

    def feed(self, chunk: bytes) -> str:
        """Feed raw bytes, return sanitized text."""
        text = self.decoder.decode(chunk)
        for char in text:
            self._process_char(char)
        return self._flush_complete_lines()

    def flush(self) -> str:
        """Flush at EOF."""
        tail = self.decoder.decode(b"", final=True)
        for char in tail:
            self._process_char(char)
        result = self._flush_complete_lines()
        if self.line_buffer:
            result += "".join(self.line_buffer)
            if not result.endswith("\n"):
                result += "\n"
            self.line_buffer = []
        return result

    def _process_char(self, char: str) -> None:
        if self.state == State.NORMAL:
            # Handle pending CR: if followed by LF, it's a line ending (CR+LF)
            # Otherwise, CR alone means "clear line" (progress bar rewrite)
            if self.pending_cr:
                self.pending_cr = False
                if char == "\n":
                    # CR+LF = line ending, output current line
                    self.output_lines.append("".join(self.line_buffer))
                    self.line_buffer = []
                    return
                else:
                    # CR alone = clear line (progress bar), then process current char
                    self.line_buffer = []
                    # Fall through to process current char

            if char == "\x1b":
                self.state = State.ESC
            elif char == "\r":
                # Don't clear yet - wait to see if followed by LF
                self.pending_cr = True
            elif char == "\n":
                # LF alone = line ending
                self.output_lines.append("".join(self.line_buffer))
                self.line_buffer = []
            elif char in ("\x07", "\x0e", "\x0f"):
                pass
            elif char == "\x08":
                if self.line_buffer:
                    self.line_buffer.pop()
            elif ord(char) >= 32 or char == "\t":
                self.line_buffer.append(char)

        elif self.state == State.ESC:
            if char == "[":
                self.state = State.CSI
            elif char == "]":
                self.state = State.OSC
            elif char in self.ESC_PREFIX_PAREN:
                self.state = State.ESC_PAREN
            elif char in self.ESC_PREFIX_HASH:
                self.state = State.ESC_HASH
            elif char in self.ESC_SINGLE:
                self.state = State.NORMAL
            else:
                self.state = State.NORMAL

        elif self.state == State.CSI:
            if 0x40 <= ord(char) <= 0x7E:
                self.state = State.NORMAL

        elif self.state == State.OSC:
            if char == "\x07":
                self.state = State.NORMAL
            elif char == "\x1b":
                self.state = State.OSC_ESC

        elif self.state == State.OSC_ESC:
            if char == "\\":
                self.state = State.NORMAL
            else:
                self.state = State.OSC

        elif self.state in (State.ESC_PAREN, State.ESC_HASH):
            self.state = State.NORMAL

    def _flush_complete_lines(self) -> str:
        if not self.output_lines:
            return ""
        result = "\n".join(self.output_lines) + "\n"
        self.output_lines = []
        return result


# =============================================================================
# DISPLAY HANDLER
# =============================================================================


class DisplayHandler:
    """Incremental UTF-8 decoder for display stream."""

    def __init__(self):
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def feed(self, chunk: bytes) -> str:
        return self.decoder.decode(chunk)

    def flush(self) -> str:
        return self.decoder.decode(b"", final=True)


# =============================================================================
# PTY SUBPROCESS RUNNER
# =============================================================================


def run_with_pexpect(
    command: list[str],
    raw_output_path: str,
    ui_callback,
) -> int:
    """Run command via PTY, streaming to UI and capture file."""
    import pexpect

    child = pexpect.spawn(command[0], command[1:], encoding=None, timeout=None)
    display = DisplayHandler()
    capture = StreamingSanitizer()

    with open(raw_output_path, "w", encoding="utf-8") as f:
        while True:
            try:
                chunk = child.read_nonblocking(size=4096, timeout=0.1)
                if chunk:
                    display_text = display.feed(chunk)
                    if display_text:
                        ui_callback(display_text)
                    capture_text = capture.feed(chunk)
                    if capture_text:
                        f.write(capture_text)
                        f.flush()
            except pexpect.TIMEOUT:
                if not child.isalive():
                    break
            except pexpect.EOF:
                break

        display.flush()
        tail = capture.flush()
        if tail:
            f.write(tail)

    child.close()
    return child.exitstatus if child.exitstatus is not None else (child.signalstatus or 1)


# =============================================================================
# PLAIN FALLBACK MODE
# =============================================================================


def run_plain_mode(command: list[str], raw_output_path: str) -> int:
    """Fallback: no TUI, print to stdout, capture to file."""
    import pexpect

    child = pexpect.spawn(command[0], command[1:], encoding=None, timeout=None)
    display = DisplayHandler()
    capture = StreamingSanitizer()

    with open(raw_output_path, "w", encoding="utf-8") as f:
        while True:
            try:
                chunk = child.read_nonblocking(size=4096, timeout=0.1)
                if chunk:
                    text = display.feed(chunk)
                    if text:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                    cap = capture.feed(chunk)
                    if cap:
                        f.write(cap)
                        f.flush()
            except pexpect.TIMEOUT:
                if not child.isalive():
                    break
            except pexpect.EOF:
                break

        display.flush()
        tail = capture.flush()
        if tail:
            f.write(tail)

    child.close()
    return child.exitstatus if child.exitstatus is not None else (child.signalstatus or 1)


# =============================================================================
# TEXTUAL UI
# =============================================================================

TEXTUAL_AVAILABLE = False
try:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, RichLog, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    pass


if TEXTUAL_AVAILABLE:

    class KiloRunnerApp(App):
        """Textual app for Kilo terminal output."""

        CSS = """
        #header-info {
            height: 3;
            background: $surface;
            padding: 0 1;
        }
        #transcript {
            height: 1fr;
        }
        #traycer-pane {
            height: auto;
            max-height: 30%;
            display: none;
            background: $primary-background;
            border-top: solid $primary;
        }
        #traycer-pane.visible {
            display: block;
        }
        """

        BINDINGS = [("q", "quit", "Quit")]

        def __init__(
            self,
            agent_name: str = "",
            model: str = "",
            timeout_display: int = 0,
            **kwargs,
        ):
            super().__init__(**kwargs)
            self.agent_name = agent_name
            self.model = model
            self.timeout_display = timeout_display
            self.start_time = time.time()
            self.exit_code: int | None = None
            self.traycer_detected = False

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(self._build_header_info(), id="header-info")
            yield Vertical(
                RichLog(id="transcript", highlight=True, markup=True),
                RichLog(id="traycer-pane"),
            )
            yield Footer()

        def _build_header_info(self) -> str:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            parts = [f"Agent: {self.agent_name or 'unknown'}"]
            if self.model:
                parts.append(f"Model: {self.model}")
            parts.append(f"Elapsed: {mins:02d}:{secs:02d}")
            if self.timeout_display:
                parts.append(f"Timeout: {self.timeout_display}s")
            return " | ".join(parts)

        def on_mount(self) -> None:
            self.set_interval(1.0, self._update_elapsed)

        def _update_elapsed(self) -> None:
            header = self.query_one("#header-info", Static)
            header.update(self._build_header_info())

        def append_output(self, text: str) -> None:
            log = self.query_one("#transcript", RichLog)
            log.write(text)
            if not self.traycer_detected and "BEGIN_TRAYCER_REPORT_MD" in text:
                self.traycer_detected = True
                pane = self.query_one("#traycer-pane", RichLog)
                pane.add_class("visible")
                pane.write("[bold green]Traycer Report Detected[/]")

        def set_exit_code(self, code: int) -> None:
            self.exit_code = code


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def check_fallback_conditions() -> tuple[bool, str]:
    """Check if we should fall back to plain mode."""
    if not TEXTUAL_AVAILABLE:
        return True, "textual not available"
    if not sys.stdout.isatty():
        return True, "stdout is not a TTY"
    try:
        import shutil

        cols, rows = shutil.get_terminal_size()
        if cols < 80 or rows < 24:
            return True, f"terminal too small ({cols}x{rows})"
    except Exception:
        pass
    return False, ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kilo Terminal Runner with rich TUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output", "-o", required=True, help="Raw output file path")
    parser.add_argument("--agent", default="", help="Agent name (display only)")
    parser.add_argument("--model", default="", help="Model name (display only)")
    parser.add_argument("--timeout", type=int, default=0, help="Timeout in seconds (display only)")
    parser.add_argument("--plain", action="store_true", help="Force plain mode (no TUI)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.command:
        print("Error: No command specified", file=sys.stderr)
        return 2

    # Strip leading '--' if present
    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if not command:
        print("Error: No command after --", file=sys.stderr)
        return 2

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check fallback conditions
    should_fallback, reason = check_fallback_conditions()
    if args.plain:
        should_fallback = True
        reason = "plain mode requested"

    if should_fallback:
        print(f"[RUNNER] Plain mode: {reason}", file=sys.stderr)
        return run_plain_mode(command, str(output_path))

    # Run with Textual UI
    app = KiloRunnerApp(
        agent_name=args.agent,
        model=args.model,
        timeout_display=args.timeout,
    )

    exit_code = 0

    async def run_subprocess():
        nonlocal exit_code
        exit_code = run_with_pexpect(
            command,
            str(output_path),
            app.append_output,
        )
        app.set_exit_code(exit_code)
        app.exit()

    import asyncio

    async def run_app():
        nonlocal exit_code
        # Run subprocess in background
        task = asyncio.create_task(run_subprocess())
        await app.run_async()
        await task

    asyncio.run(run_app())
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
