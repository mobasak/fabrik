"""
Fabrik WordPress Resolved Spec

ResolvedSpec is the immutable result of loading and merging all spec layers.
Used as input to the planning and manifest generation pipeline.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import InitVar, dataclass, field
from typing import Any


def load_spec(site_id: str) -> dict:
    """
    Load merged spec for a site.

    Args:
        site_id: Site domain (e.g., ocoron.com)

    Returns:
        Fully merged spec dict
    """
    from fabrik.wordpress.spec_loader import SpecLoader

    loader = SpecLoader(site_id)
    return loader.load()


@dataclass(frozen=True)
class ResolvedSpec:
    """
    Immutable resolved site specification.

    Attributes:
        site_id: Site domain (e.g., ocoron.com)
        data: Fully merged, normalized spec dict (read-only copy)
        spec_hash: SHA256 hash excluding secrets (computed automatically)
    """

    site_id: str
    data: InitVar[dict[str, Any]]
    spec_hash: str = field(default="")
    _data: dict[str, Any] = field(init=False, repr=False)

    SECRET_KEY_PATTERNS: tuple[str, ...] = field(
        default=("password", "secret", "token", "key", "credential"),
        init=False,
        repr=False,
    )

    def __post_init__(self, data: dict[str, Any]) -> None:
        """Compute spec_hash if not provided and enforce immutability."""
        object.__setattr__(self, "_data", copy.deepcopy(data))
        if not self.spec_hash:
            object.__setattr__(self, "spec_hash", self._compute_hash())

    @property
    def data(self) -> dict[str, Any]:
        """Return a defensive copy of the internal data."""
        return copy.deepcopy(self._data)

    def _compute_hash(self) -> str:
        """Compute SHA256 hash of spec excluding secrets."""
        sanitized = self.exclude_secrets()
        serialized = json.dumps(sanitized, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def exclude_secrets(self) -> dict[str, Any]:
        """
        Return a deep copy of spec with secret keys removed.

        Returns:
            Sanitized spec dict
        """

        def _exclude_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    # Skip keys that match secret patterns
                    if any(pat in k.lower() for pat in self.SECRET_KEY_PATTERNS):
                        continue
                    result[k] = _exclude_recursive(v)
                return result
            elif isinstance(obj, list):
                return [_exclude_recursive(item) for item in obj]
            else:
                return copy.deepcopy(obj)

        return _exclude_recursive(self._data)

    @classmethod
    def from_site(cls, site_id: str) -> ResolvedSpec:
        """
        Load and resolve spec for a site.

        Args:
            site_id: Site domain (e.g., ocoron.com)

        Returns:
            ResolvedSpec instance with computed hash
        """
        data = load_spec(site_id)
        return cls(site_id=site_id, data=data, spec_hash="")
