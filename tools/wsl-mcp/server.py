#!/usr/bin/env python3
"""wsl-mcp — one MCP server that gives Claude Desktop full access to this WSL box.

Transport: streamable-HTTP on 127.0.0.1:8040 (systemd unit `wsl-mcp.service`).
Claude Desktop reaches it through a Windows-native `npx mcp-remote` stdio bridge,
so Desktop never spawns `wsl.exe` and nothing here depends on the Desktop build.
Claude Code can point at the same URL with `{"type":"http"}`.

Tools: bash, read_file, write_file, edit_file, list_dir.
`bash` accepts BOTH `description` and `comment` (either is ignored) so the old
"never send description to wsl-shell" quirk is gone.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("WSL_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("WSL_MCP_PORT", "8040"))
DEFAULT_CWD = os.environ.get("WSL_MCP_DEFAULT_CWD", str(Path.home()))
MAX_OUTPUT = int(os.environ.get("WSL_MCP_MAX_OUTPUT", "200000"))  # chars kept per stream

mcp = FastMCP(
    "wsl",
    instructions=(
        "Full access to the operator's WSL Ubuntu workstation (/opt repos, scripts, "
        "docker, ssh vps). Use `bash` for commands and the file tools for edits."
    ),
    host=HOST,
    port=PORT,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


def _clip(text: str, limit: int = MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2):]
    return f"{head}\n\n... [truncated {len(text) - limit} chars] ...\n\n{tail}"


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(DEFAULT_CWD) / p
    return p


@mcp.tool()
async def bash(
    command: str,
    description: Optional[str] = None,
    comment: Optional[str] = None,
    timeout_seconds: int = 120,
    working_directory: Optional[str] = None,
    stdin: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Run a shell command in WSL as the operator (login bash, full PATH).

    Returns stdout, stderr, exit_code, timed_out, cwd. `description` and
    `comment` are both accepted and ignored. For jobs longer than
    timeout_seconds (max 3600) run them detached: `setsid nohup ... &`.
    """
    timeout_seconds = max(1, min(int(timeout_seconds), 3600))
    cwd = str(_resolve(working_directory)) if working_directory else DEFAULT_CWD
    if not Path(cwd).is_dir():
        return {"error": f"working_directory does not exist: {cwd}", "exit_code": -1}
    run_env = dict(os.environ)
    if env:
        run_env.update({str(k): str(v) for k, v in env.items()})

    proc = await asyncio.create_subprocess_exec(
        "/bin/bash", "-lc", command,
        cwd=cwd, env=run_env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin.encode() if stdin else None), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        timed_out = True
        for sig in (15, 9):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=5)
                break
            except asyncio.TimeoutError:
                out, err = b"", b""
    return {
        "stdout": _clip(out.decode(errors="replace")),
        "stderr": _clip(err.decode(errors="replace")),
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "cwd": cwd,
    }


@mcp.tool()
def read_file(path: str, offset: int = 0, limit: int = 0) -> str:
    """Read a text file, line-numbered like `cat -n`. `offset` = first line
    (1-based, 0 = start); `limit` = max lines (0 = all)."""
    p = _resolve(path)
    if not p.is_file():
        return f"ERROR: not a file: {p}"
    lines = p.read_text(errors="replace").splitlines()
    start = max(offset - 1, 0) if offset else 0
    end = start + limit if limit else len(lines)
    chunk = lines[start:end]
    body = "\n".join(f"{i:6d}\t{l}" for i, l in enumerate(chunk, start=start + 1))
    note = f"\n[{len(lines)} lines total]" if end < len(lines) or start else ""
    return _clip(body) + note


@mcp.tool()
def write_file(path: str, content: str, mkdirs: bool = True, overwrite: bool = True) -> str:
    """Create or overwrite a text file (UTF-8). Creates parent dirs by default."""
    p = _resolve(path)
    if p.exists() and not overwrite:
        return f"ERROR: exists and overwrite=false: {p}"
    if mkdirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content.encode())} bytes to {p}"


@mcp.tool()
def edit_file(path: str, old_str: str, new_str: str, replace_all: bool = False) -> str:
    """Replace `old_str` with `new_str` in a file. `old_str` must match exactly
    once unless replace_all=true."""
    p = _resolve(path)
    if not p.is_file():
        return f"ERROR: not a file: {p}"
    text = p.read_text(errors="replace")
    n = text.count(old_str)
    if n == 0:
        return "ERROR: old_str not found"
    if n > 1 and not replace_all:
        return f"ERROR: old_str matches {n} times; pass replace_all=true or widen old_str"
    new_text = text.replace(old_str, new_str) if replace_all else text.replace(old_str, new_str, 1)
    p.write_text(new_text, encoding="utf-8")
    return f"replaced {n if replace_all else 1} occurrence(s) in {p}"


@mcp.tool()
def list_dir(path: str = ".", depth: int = 1, show_hidden: bool = False) -> str:
    """List a directory (dirs first, file sizes), up to `depth` levels."""
    root = _resolve(path)
    if not root.is_dir():
        return f"ERROR: not a directory: {root}"
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
    out: list[str] = []

    def walk(d: Path, level: int) -> None:
        try:
            entries = sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            out.append(f"{'  ' * level}[permission denied] {d}")
            return
        for e in entries:
            if not show_hidden and e.name.startswith("."):
                continue
            if e.is_dir():
                out.append(f"{'  ' * level}{e.name}/")
                if level + 1 < depth and e.name not in skip:
                    walk(e, level + 1)
            else:
                try:
                    size = e.stat().st_size
                except OSError:
                    size = -1
                out.append(f"{'  ' * level}{e.name}  ({size} B)")

    walk(root, 0)
    return _clip(f"{root}\n" + "\n".join(out))


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
