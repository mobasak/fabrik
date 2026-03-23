"""Scenario 07: Large change with many utility functions."""

import datetime
import math
import re


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    cut = max_length - len(suffix)
    if cut <= 0:
        return suffix[:max_length]
    return text[:cut] + suffix


def camel_to_snake(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    result = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", result)
    return result.lower()


def snake_to_camel(name: str, pascal: bool = False) -> str:
    """Convert snake_case to camelCase or PascalCase."""
    parts = name.split("_")
    if pascal:
        return "".join(p.capitalize() for p in parts)
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def chunk_list(items: list, size: int) -> list[list]:
    """Split a list into chunks of the given size."""
    if size <= 0:
        raise ValueError("Chunk size must be positive")
    chunks = []
    for i in range(0, len(items), size):
        chunks.append(items[i : i + size])
    return chunks


def flatten(nested: list) -> list:
    """Flatten a nested list one level deep."""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def deduplicate(items: list) -> list:
    """Remove duplicates while preserving order."""
    seen: set = set()
    result = []
    for item in items:
        key = id(item) if not isinstance(item, (str, int, float)) else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = seconds % 60
    if minutes < 60:
        return f"{minutes}m {remaining:.0f}s"
    hours = minutes // 60
    remaining_min = minutes % 60
    return f"{hours}h {remaining_min}m"


def parse_iso_date(date_str: str) -> datetime.datetime:
    """Parse an ISO 8601 date string to datetime."""
    date_str = date_str.strip()
    if date_str.endswith("Z"):
        date_str = date_str[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(date_str)


def days_between(start: datetime.date, end: datetime.date) -> int:
    """Calculate the number of days between two dates."""
    delta = end - start
    return abs(delta.days)


def is_weekend(date: datetime.date) -> bool:
    """Check if a date falls on Saturday or Sunday."""
    return date.weekday() >= 5


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a value between minimum and maximum."""
    if minimum > maximum:
        raise ValueError("minimum must be <= maximum")
    return max(minimum, min(maximum, value))


def round_to(value: float, precision: int = 2) -> float:
    """Round a float to the specified number of decimal places."""
    factor = math.pow(10, precision)
    return math.floor(value * factor + 0.5) / factor


def percentage(part: float, total: float) -> float:
    """Calculate percentage with safe division."""
    if total == 0:
        return 0.0
    return round_to((part / total) * 100, 2)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide with a fallback value when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator
