#!/usr/bin/env python3
# AFTER-EDIT: none
"""
Kilo Terminal Runner - Rich TUI for Kilo CLI agent wrappers.

Replaces tee-based streaming with a full-screen Textual UI while preserving
the raw output file format for Traycer report extraction.

Usage:
    python kilo_terminal_runner.py --output /tmp/output.txt -- kilo run ...

Fallback:
    If Textual import fails or terminal too small, falls back to plain mode.

Workflow Doc: docs/workflows/KILO_AGENT_MANAGEMENT.md
  ⚠️  Update the workflow doc when modifying this script.
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
        self.partial_written = 0  # Track partial line_buffer chars already flushed to disk
        self._skip_partial_prefix = 0  # Chars to skip in next _flush_complete_lines

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
        # Handle pending CR at EOF (edge case: stream ends with bare CR)
        if self.pending_cr:
            self.pending_cr = False
            self.line_buffer = []
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
                    if self.partial_written > 0:
                        self._skip_partial_prefix = self.partial_written
                    self.line_buffer = []
                    self.partial_written = 0
                    return
                else:
                    # CR alone = clear line (progress bar), then process current char
                    self.line_buffer = []
                    self.partial_written = 0
                    # Fall through to process current char

            if char == "\x1b":
                self.state = State.ESC
            elif char == "\r":
                # Don't clear yet - wait to see if followed by LF
                self.pending_cr = True
            elif char == "\n":
                # LF alone = line ending
                self.output_lines.append("".join(self.line_buffer))
                if self.partial_written > 0:
                    self._skip_partial_prefix = self.partial_written
                self.line_buffer = []
                self.partial_written = 0
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
        # If partial content was already written to disk on a TIMEOUT flush,
        # the first line in result is a continuation — just append the newline
        if self._skip_partial_prefix > 0:
            # The partial content is already on disk; just write what's new
            result = result[self._skip_partial_prefix :]
            self._skip_partial_prefix = 0
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


class DisplayAnsiBuffer:
    """
    ANSI sequence buffer for display rendering.

    Ensures complete ANSI sequences are passed to Rich's AnsiDecoder.
    Holds incomplete sequences until next chunk arrives.

    Uses local state per scan (not persistent) because the retained buffer
    already contains the incomplete introducer bytes that need rescanning.
    """

    def __init__(self):
        self.buffer = ""
        self.safe_end = 0  # Index up to which buffer is safe to emit

    def feed(self, text: str) -> str:
        """Feed text, return ANSI-safe portion for rendering."""
        self.buffer += text
        self._scan()
        if self.safe_end > 0:
            safe = self.buffer[: self.safe_end]
            self.buffer = self.buffer[self.safe_end :]
            self.safe_end = 0
            return safe
        return ""

    def flush(self) -> str:
        """Flush remaining buffer at EOF."""
        result = self.buffer
        self.buffer = ""
        self.safe_end = 0
        return result

    def _scan(self) -> None:
        """Scan buffer and mark safe_end at last complete sequence boundary."""
        # Use local state - buffer already contains incomplete introducers
        state = State.NORMAL
        i = 0
        last_safe = 0
        while i < len(self.buffer):
            char = self.buffer[i]

            if state == State.NORMAL:
                if char == "\x1b":
                    state = State.ESC
                else:
                    last_safe = i + 1

            elif state == State.ESC:
                if char == "[":
                    state = State.CSI
                elif char == "]":
                    state = State.OSC
                elif char in "()":
                    state = State.ESC_PAREN
                elif char == "#":
                    state = State.ESC_HASH
                elif char in "78=>cDEHMNOPVWXZ\\^_":
                    # Single-char ESC sequences - complete
                    state = State.NORMAL
                    last_safe = i + 1
                else:
                    # Unknown ESC sequence, treat as complete
                    state = State.NORMAL
                    last_safe = i + 1

            elif state == State.CSI:
                # CSI ends with byte in 0x40-0x7E range
                if 0x40 <= ord(char) <= 0x7E:
                    state = State.NORMAL
                    last_safe = i + 1

            elif state == State.OSC:
                if char == "\x07":  # BEL terminates OSC
                    state = State.NORMAL
                    last_safe = i + 1
                elif char == "\x1b":
                    state = State.OSC_ESC

            elif state == State.OSC_ESC:
                if char == "\\":  # ESC \ terminates OSC
                    state = State.NORMAL
                    last_safe = i + 1
                else:
                    state = State.OSC

            elif state in (State.ESC_PAREN, State.ESC_HASH):
                # These consume one more char then complete
                state = State.NORMAL
                last_safe = i + 1

            i += 1

        self.safe_end = last_safe


# =============================================================================
# PTY SUBPROCESS RUNNER
# =============================================================================


def run_with_pexpect(
    command: list[str],
    raw_output_path: str,
    ui_callback,
    ui_flush_callback=None,
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
                # Flush incomplete line buffer on idle so output file stays current
                if capture.line_buffer and len(capture.line_buffer) > capture.partial_written:
                    new_chars = "".join(capture.line_buffer[capture.partial_written :])
                    f.write(new_chars)
                    f.flush()
                    capture.partial_written = len(capture.line_buffer)
                # Check if process exited - use eof() which is more reliable than isalive()
                # isalive() can return True if child processes still running
                if child.eof() or not child.isalive():
                    break
            except pexpect.EOF:
                break

        # Flush remaining display text and notify UI
        display_tail = display.flush()
        if display_tail:
            ui_callback(display_tail)
        if ui_flush_callback:
            ui_flush_callback()

        tail = capture.flush()
        if tail:
            f.write(tail)

    # Wait for process to fully terminate and get exit status
    child.wait()
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
                # Flush incomplete line buffer on idle so output file stays current
                if capture.line_buffer and len(capture.line_buffer) > capture.partial_written:
                    new_chars = "".join(capture.line_buffer[capture.partial_written :])
                    f.write(new_chars)
                    f.flush()
                    capture.partial_written = len(capture.line_buffer)
                # Check if process exited - use eof() which is more reliable than isalive()
                if child.eof() or not child.isalive():
                    break
            except pexpect.EOF:
                break

        # Flush remaining display text
        display_tail = display.flush()
        if display_tail:
            sys.stdout.write(display_tail)
            sys.stdout.flush()

        tail = capture.flush()
        if tail:
            f.write(tail)

    # Wait for process to fully terminate and get exit status
    child.wait()
    child.close()
    return child.exitstatus if child.exitstatus is not None else (child.signalstatus or 1)


# =============================================================================
# TEXTUAL UI
# =============================================================================

TEXTUAL_AVAILABLE = False
try:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import RichLog, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    pass


if TEXTUAL_AVAILABLE:
    from rich.ansi import AnsiDecoder

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
        #status-info {
            height: 1;
            background: $surface;
            padding: 0 1;
            color: $text-muted;
        }
        """

        BINDINGS = [
            ("ctrl+y", "copy_output", "Copy transcript to clipboard"),
            ("ctrl+s", "save_transcript", "Save transcript to file"),
        ]

        def __init__(
            self,
            agent_name: str = "",
            model: str = "",
            role: str = "",
            variant: str = "",
            session_title: str = "",
            timeout_display: int = 0,
            output_path: str = "",
            **kwargs,
        ):
            super().__init__(**kwargs)
            self.agent_name = agent_name
            self.model = model
            self.role = role
            self.variant = variant
            self.session_title = session_title
            self.timeout_display = timeout_display
            self.output_path = output_path
            self.start_time = time.time()
            self.exit_code: int | None = None
            self.traycer_detected = False
            self.in_traycer_report = False
            self.ansi_decoder = AnsiDecoder()
            self.display_ansi_buffer = DisplayAnsiBuffer()  # Stateful ANSI buffer
            self.ui_line_buffer = ""  # Chunk-safe line buffering for Traycer detection
            self.traycer_buffer: list[str] = []  # Preserve report formatting

        def compose(self) -> ComposeResult:
            yield Static(self._build_header_info(), id="header-info")
            yield Vertical(
                RichLog(id="transcript", highlight=True, markup=True),
                RichLog(id="traycer-pane"),
            )
            yield Static(self._build_status_info(), id="status-info")

        def _build_header_info(self) -> str:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            parts = [f"Agent: {self.agent_name or 'unknown'}"]
            if self.model:
                parts.append(f"Model: {self.model}")
            if self.role:
                parts.append(f"Role: {self.role}")
            if self.variant:
                parts.append(f"Variant: {self.variant}")
            parts.append(f"Elapsed: {mins:02d}:{secs:02d}")
            if self.session_title:
                parts.append(f"Session: {self.session_title}")
            return " | ".join(parts)

        def _build_status_info(self) -> str:
            parts = []
            if self.output_path:
                parts.append(f"Raw: {self.output_path}")
            exit_str = str(self.exit_code) if self.exit_code is not None else "running"
            parts.append(f"Exit: {exit_str}")
            parts.append(f"Report: {'YES' if self.traycer_detected else 'NO'}")
            if self.timeout_display:
                parts.append(f"Timeout: {self.timeout_display}s")
            parts.append("Ctrl+Y=Copy | Ctrl+S=Save")
            return " | ".join(parts)

        def on_mount(self) -> None:
            self.set_interval(1.0, self._update_ui)

        def _update_ui(self) -> None:
            self.query_one("#header-info", Static).update(self._build_header_info())
            self.query_one("#status-info", Static).update(self._build_status_info())

        def append_output(self, text: str) -> None:
            """Append output to transcript and detect/display Traycer report."""
            transcript = self.query_one("#transcript", RichLog)
            traycer = self.query_one("#traycer-pane", RichLog)

            # Chunk-safe ANSI buffering via stateful parser
            safe_text = self.display_ansi_buffer.feed(text)

            # Decode ANSI sequences for proper rendering in transcript
            if safe_text:
                for segment in self.ansi_decoder.decode(safe_text):
                    transcript.write(segment)

            # Normalize line endings for UI parsing: CR+LF -> LF, bare CR -> remove
            normalized = text.replace("\r\n", "\n").replace("\r", "")
            self.ui_line_buffer += normalized
            lines = self.ui_line_buffer.split("\n")
            self.ui_line_buffer = lines.pop()  # Keep partial tail for next chunk

            # Process only complete lines for Traycer detection
            for line in lines:
                if "BEGIN_TRAYCER_REPORT_MD" in line:
                    self.traycer_detected = True
                    self.in_traycer_report = True
                    self.traycer_buffer = []
                    traycer.add_class("visible")
                    self._update_ui()  # Refresh status to show Report: YES
                    continue

                if "END_TRAYCER_REPORT_MD" in line:
                    self.in_traycer_report = False
                    continue

                if self.in_traycer_report:
                    # Buffer report lines (including empty) and render with preserved formatting
                    self.traycer_buffer.append(line)
                    traycer.clear()
                    traycer.write("\n".join(self.traycer_buffer))

        def set_exit_code(self, code: int) -> None:
            self.exit_code = code
            self._update_ui()  # Refresh status to show final exit code

        def action_copy_output(self) -> None:
            """Copy raw output to clipboard (Ctrl+Y)."""
            try:
                if self.output_path and Path(self.output_path).exists():
                    content = Path(self.output_path).read_text(encoding="utf-8")
                    import subprocess

                    # Try xclip first (X11), then xsel, then wl-copy (Wayland)
                    for cmd in [
                        ["xclip", "-selection", "clipboard"],
                        ["xsel", "--clipboard", "--input"],
                        ["wl-copy"],
                    ]:
                        try:
                            proc = subprocess.run(
                                cmd, input=content, text=True, capture_output=True, timeout=5
                            )
                            if proc.returncode == 0:
                                self.notify(
                                    f"✓ Copied {len(content)} chars to clipboard",
                                    severity="information",
                                )
                                return
                        except (FileNotFoundError, subprocess.TimeoutExpired):
                            continue
                    self.notify(
                        "✗ No clipboard tool found (xclip/xsel/wl-copy)", severity="warning"
                    )
                else:
                    self.notify("✗ Output file not ready yet", severity="warning")
            except Exception as e:
                self.notify(f"✗ Copy failed: {e}", severity="error")

        def action_save_transcript(self) -> None:
            """Save transcript to timestamped file (Ctrl+S)."""
            try:
                if self.output_path and Path(self.output_path).exists():
                    content = Path(self.output_path).read_text(encoding="utf-8")
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    save_path = Path(".droid") / f"transcript-{timestamp}.txt"
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_text(content, encoding="utf-8")
                    self.notify(f"✓ Saved to {save_path}", severity="information")
                else:
                    self.notify("✗ Output file not ready yet", severity="warning")
            except Exception as e:
                self.notify(f"✗ Save failed: {e}", severity="error")

        def flush_pending_ui(self) -> None:
            """Flush any pending UI buffers at EOF."""
            try:
                transcript = self.query_one("#transcript", RichLog)
                traycer = self.query_one("#traycer-pane", RichLog)

                # Flush remaining ANSI buffer via stateful parser
                remaining = self.display_ansi_buffer.flush()
                if remaining:
                    for segment in self.ansi_decoder.decode(remaining):
                        transcript.write(segment)

                # Process final partial line for Traycer detection
                if self.ui_line_buffer:
                    line = self.ui_line_buffer
                    self.ui_line_buffer = ""

                    if "BEGIN_TRAYCER_REPORT_MD" in line:
                        self.traycer_detected = True
                        self.in_traycer_report = True
                        self.traycer_buffer = []
                        traycer.add_class("visible")
                        self._update_ui()
                    elif "END_TRAYCER_REPORT_MD" in line:
                        self.in_traycer_report = False
                    elif self.in_traycer_report:
                        self.traycer_buffer.append(line)
                        traycer.clear()
                        traycer.write("\n".join(self.traycer_buffer))
            except Exception as e:
                # Log but don't crash - raw output file is already complete
                print(f"[RUNNER] flush_pending_ui warning: {e}", file=sys.stderr)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def check_fallback_conditions() -> tuple[bool, str]:
    """Check if we should fall back to plain mode."""
    if not TEXTUAL_AVAILABLE:
        return True, "textual not available"
    # Validate pexpect availability early
    try:
        import pexpect  # noqa: F401
    except ImportError:
        return True, "pexpect not available"
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
    parser.add_argument("--role", default="", help="Role (display only)")
    parser.add_argument("--variant", default="", help="Variant (display only)")
    parser.add_argument("--session-title", default="", help="Session title (display only)")
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
        exit_code = run_plain_mode(command, str(output_path))
    else:
        # Run with Textual UI
        from threading import Thread

        app = KiloRunnerApp(
            agent_name=args.agent,
            model=args.model,
            role=args.role,
            variant=args.variant,
            session_title=args.session_title,
            timeout_display=args.timeout,
            output_path=str(output_path),
        )

        exit_code = 0

        def worker():
            """Background thread for PTY subprocess - keeps UI responsive."""
            nonlocal exit_code
            try:
                exit_code = run_with_pexpect(
                    command,
                    str(output_path),
                    lambda text: app.call_from_thread(app.append_output, text),
                    lambda: app.call_from_thread(app.flush_pending_ui),
                )
            except Exception as e:
                exit_code = 1
                app.call_from_thread(app.append_output, f"\n[RUNNER ERROR] {e}\n")
            finally:
                app.call_from_thread(app.set_exit_code, exit_code)
                app.call_from_thread(app.exit)

        Thread(target=worker, daemon=True).start()
        app.run()

        # Ensure terminal is fully reset after Textual exits
        # This helps IDE terminals detect process completion
        sys.stdout.write("\033[?1049l")  # Exit alternate screen buffer
        sys.stdout.write("\033[0m")  # Reset all attributes
        sys.stdout.flush()

    # Auto-save transcript to .droid/ for analysis after TUI closes
    save_file = None
    try:
        if output_path.exists():
            content = output_path.read_text(encoding="utf-8")
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            agent_slug = args.agent.replace(" ", "-")[:30] if args.agent else "unknown"
            save_dir = Path(".droid/transcripts")
            save_dir.mkdir(parents=True, exist_ok=True)
            save_file = save_dir / f"{timestamp}-{agent_slug}-exit{exit_code}.txt"
            save_file.write_text(content, encoding="utf-8")
            print(f"[RUNNER] Transcript saved: {save_file}", file=sys.stderr)
    except Exception as e:
        print(f"[RUNNER] Auto-save failed: {e}", file=sys.stderr)

    # Auto-log to dev_tracker.db for centralized metrics
    try:
        import json
        import subprocess

        event_data = json.dumps(
            {
                "agent": args.agent or "unknown",
                "exit_code": exit_code,
                "model": args.model or "unknown",
                "role": args.role or "unknown",
                "transcript_file": str(save_file) if save_file else str(output_path),
            }
        )
        tracker_script = Path(__file__).parent / "dev_tracker.py"
        if tracker_script.exists():
            subprocess.run(
                [sys.executable, str(tracker_script), "log", "agent_run", event_data],
                capture_output=True,
                timeout=5,
            )
    except Exception as e:
        print(f"[RUNNER] dev_tracker log failed: {e}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
