# AFTER-EDIT: none
"""The ``.env`` codec — compose's dotenv grammar, for every Fabrik writer and reader of a ``.env``.

Measured against docker compose 2.40.3 (W-2ae286e2): an unquoted or double-quoted ``$`` is
interpolated (``K=a$b`` reaches the container as ``a``), single quotes are literal, and inside
double quotes ``\\n \\r \\t \\\\ \\" \\$`` are escapes while any other ``\\x`` stays two characters.

A value's ``$`` means one of two things, and the file records which (D-row in DECISIONS):

- a LITERAL (a secret, a registrar value, an override) — written single-quoted, or with ``\\$``
  inside double quotes, so compose delivers it byte-identical;
- a TEMPLATE (a spec ``env:`` value such as ``${LOG_LEVEL:-INFO}``) — an :class:`EnvTemplate`,
  written with a bare ``$`` so compose interpolates it. A template the reader found in a file
  keeps its original bytes in ``source`` and is written back verbatim.

``str()``, f-strings and slicing turn an :class:`EnvTemplate` back into a plain ``str`` (a
literal); that is how a secret read from a file is made literal on purpose.
"""

from __future__ import annotations

_DQ_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "$": "$"}
_QUOTE_TRIGGERS = (" ", "#", "'", '"', "\n", "\r", "\t", "\\")


class EnvTemplate(str):
    """A value whose ``$`` compose must interpolate. ``source`` = its bytes as read from a file."""

    source: str | None

    def __new__(cls, value: str, source: str | None = None) -> EnvTemplate:
        obj = super().__new__(cls, value)
        obj.source = source
        return obj


def format_value(value: str) -> str:
    """The right-hand side of one ``KEY=`` line."""
    if isinstance(value, EnvTemplate) and value.source is not None:
        return value.source
    template = isinstance(value, EnvTemplate)
    if not any(c in value for c in _QUOTE_TRIGGERS) and (template or "$" not in value):
        return value
    if not template and "$" in value and not any(c in value for c in ("'", "\\", "\n", "\r")):
        return f"'{value}'"
    out = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    if not template:
        out = out.replace("$", "\\$")
    return f'"{out}"'


def format_env_line(key: str, value: str) -> str:
    """One ``KEY=value`` line. Raises ``ValueError`` — naming the key, never the value — when the line
    holds a NUL byte (runc refuses the container; dotenv has no escape for it) or is not UTF-8 (a lone
    surrogate the writer cannot encode), the refusals D-1269 makes for compose ``environment:``. The
    EMITTED line is checked, so the key and a kept template ``source`` are covered with the value."""
    line = f"{key}={format_value(value)}"
    if "\x00" in line:
        raise ValueError(f"the .env line for {key!r} contains a NUL byte")
    try:
        line.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"the .env line for {key!r} is not valid UTF-8") from None
    return line


def format_env(env: dict[str, str]) -> str:
    """Format a mapping as ``.env`` content, keys sorted."""
    lines = [format_env_line(key, value) for key, value in sorted(env.items())]
    return "\n".join(lines) + "\n" if lines else ""


def _read_quoted(text: str, start: int) -> tuple[str, int, bool]:
    """Read the quoted value opening at ``text[start]``: ``(value, index after the closing quote,
    holds an unescaped $)``. Raises ``ValueError`` when the quote never closes."""
    quote, i, dollar = text[start], start + 1, False
    out: list[str] = []
    while i < len(text):
        c = text[i]
        if c == quote:
            return "".join(out), i + 1, dollar
        if c == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if quote == "'":
                out.append("'" if nxt == "'" else c + nxt if nxt == "\\" else c)
                i += 2 if nxt in ("'", "\\") else 1
                continue
            out.append(_DQ_ESCAPES.get(nxt, c + nxt))
            i += 2
            continue
        if c == "$" and quote == '"':
            dollar = True
        out.append(c)
        i += 1
    # Never the value in the message: it is a secret, and the error reaches logs and the terminal.
    raise ValueError("unterminated quoted value")


def parse_env(content: str) -> dict[str, str]:
    """Parse ``.env`` content as compose does; a value holding an unescaped ``$`` comes back as an
    :class:`EnvTemplate`. Raises ``ValueError`` — naming the key and line, never the value — on an
    unterminated quote or a quote character after the closing quote (compose refuses both files).
    """
    result: dict[str, str] = {}
    pos, n = 0, len(content)
    while pos < n:
        lineno = content.count("\n", 0, pos) + 1
        end = content.find("\n", pos)
        end = n if end < 0 else end
        line = content[pos:end]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            pos = end + 1
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        lead = len(rest) - len(rest.lstrip(" \t"))
        vstart = pos + len(line) - len(rest) + lead
        if vstart < n and content[vstart] in ("'", '"'):
            try:
                value, after, dollar = _read_quoted(content, vstart)
            except ValueError as e:
                raise ValueError(f"{e} for {key} at line {lineno}") from None
            tail_end = content.find("\n", after)
            tail_end = n if tail_end < 0 else tail_end
            # Compose ignores `K="v" junk` and `K="v" # c` and refuses a quote in the tail, which
            # is refused here too; it also refuses some other tail words (`K="v" x#c`) that this
            # reader still reads as `v` (W-2ae286e2 review, recorded: leniency, the quoted content
            # is kept).
            if any(q in content[after:tail_end].split("#", 1)[0] for q in ("'", '"')):
                raise ValueError(f"a quote after the closing quote for {key} at line {lineno}")
            source = content[vstart:after]
            result[key] = EnvTemplate(value, source) if dollar else value
            pos = tail_end + 1
            continue
        value = rest.lstrip(" \t")
        if value.endswith("\r"):
            value = value[:-1]
        cut = value.find(" #")
        if cut >= 0:
            value = value[:cut]
        value = value.rstrip(" \t")
        result[key] = EnvTemplate(value, value) if "$" in value else value
        pos = end + 1
    return result
