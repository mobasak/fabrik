"""
Fabrik WordPress Spec Validator

Validates site specifications according to schema/VALIDATION_RULES.md
"""

import re
from typing import Any


class ValidationError(Exception):
    """Spec validation failed."""

    pass


class SpecValidator:
    """Validate WordPress site specifications."""

    def __init__(self, spec: dict):
        """
        Initialize validator.

        Args:
            spec: Merged spec dict
        """
        self.spec = spec
        self.errors = []
        self.warnings = []

    def validate(self) -> tuple[list[str], list[str]]:
        """
        Run all validations.

        Returns:
            Tuple of (errors, warnings)
        """
        # 1. Required fields
        self._validate_required()

        # 2. Types
        self._validate_types()

        # 3. References
        self._validate_references()

        # 4. Localization
        self._validate_localization()

        # 5. Conflicts
        self._validate_conflicts()

        return self.errors, self.warnings

    def fail_fast(self):
        """Raise exception on first error."""
        errors, warnings = self.validate()

        if errors:
            error_msg = "Spec validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValidationError(error_msg)

        # Log warnings
        if warnings:
            for warning in warnings:
                print(f"⚠️  {warning}")

    def _validate_required(self):
        """Validate required fields are present."""
        required = [
            ("schema_version", int),
            ("site.domain", str),
            ("brand.name", str),
            ("contact.email", str),
            ("languages.primary", str),
            ("deployment.target", str),
        ]

        for path, expected_type in required:
            value = self._get_nested(path)
            if value is None:
                self.errors.append(f"Missing required field: {path}")
            elif not isinstance(value, expected_type):
                self.errors.append(
                    f"{path}: expected {expected_type.__name__}, got {type(value).__name__}"
                )

    def _validate_types(self):
        """Validate field types."""
        # Email format
        email = self._get_nested("contact.email")
        if email and not self._is_valid_email(email):
            self.errors.append(f"contact.email: invalid email format '{email}'")

        # Color format
        colors = self._get_nested("brand.colors", {})
        for color_name, color_value in colors.items():
            if color_value and not self._is_valid_color(color_value):
                self.errors.append(
                    f"brand.colors.{color_name}: invalid color format '{color_value}'"
                )

        # Locale format
        primary = self._get_nested("languages.primary")
        if primary and not self._is_valid_locale(primary):
            self.errors.append(f"languages.primary: invalid locale format '{primary}'")

    def _validate_references(self):
        """Validate all references resolve."""
        # Check page sections
        pages = self._get_nested("pages", [])
        for i, page in enumerate(pages):
            sections = page.get("sections", [])
            for j, section in enumerate(sections):
                path = f"pages[{i}].sections[{j}]"

                # items_ref
                if "items_ref" in section and not section.get("items"):
                    ref = section["items_ref"]
                    if not self._resolve_ref(ref):
                        self.errors.append(f"{path}: reference '{ref}' not found")

                # content_ref
                if "content_ref" in section and not section.get("content"):
                    ref = section["content_ref"]
                    if ref.startswith("entity."):
                        # entity.* refs only valid in entity templates
                        # We'll validate this during page generation
                        pass
                    elif not self._resolve_ref(ref):
                        self.errors.append(f"{path}: reference '{ref}' not found")

    def _validate_localization(self):
        """Validate localization completeness."""
        primary = self._get_nested("languages.primary")
        additional = self._get_nested("languages.additional", [])
        allowed_locales = [primary] + additional

        # Find all localized strings
        localized = self._find_localized_strings(self.spec)

        for path, value in localized:
            # Check primary locale exists
            if primary not in value:
                self.errors.append(f"{path}: missing primary locale '{primary}'")

            # Check all locale keys are valid
            for locale in value.keys():
                if locale not in allowed_locales:
                    self.errors.append(f"{path}: locale '{locale}' not in languages list")

    def _validate_conflicts(self):
        """Validate no conflicts (duplicate slugs, etc)."""
        # Collect all page slugs
        slugs = {}

        def collect_slugs(pages: list, source: str = "explicit"):
            for page in pages:
                slug = page.get("slug", "")
                if slug in slugs:
                    self.warnings.append(
                        f"Duplicate slug '{slug}' (sources: {slugs[slug]}, {source})"
                    )
                else:
                    slugs[slug] = source

                # Recurse for children
                children = page.get("children", [])
                if children:
                    collect_slugs(children, source)

        pages = self._get_nested("pages", [])
        collect_slugs(pages, "explicit")

    def _get_nested(self, path: str, default: Any = None) -> Any:
        """Get nested value from spec using dot notation."""
        keys = path.split(".")
        value = self.spec

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default

            if value is None:
                return default

        return value

    def _resolve_ref(self, ref: str) -> bool:
        """Check if reference resolves to a value."""
        value = self._get_nested(ref)
        return value is not None

    def _find_localized_strings(self, obj: Any, path: str = "") -> list[tuple[str, dict]]:
        """Find all localized strings (dicts with locale keys)."""
        results = []

        if isinstance(obj, dict):
            # Check if this looks like a localized string
            if self._is_localized_string(obj):
                results.append((path, obj))
            else:
                # Recurse
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    results.extend(self._find_localized_strings(value, new_path))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                results.extend(self._find_localized_strings(item, new_path))

        return results

    def _is_localized_string(self, obj: dict) -> bool:
        """Check if dict looks like a localized string."""
        if not isinstance(obj, dict):
            return False

        # Check if all keys look like locales (en_US, tr_TR, etc)
        locale_pattern = r"^[a-z]{2}_[A-Z]{2}$"
        return all(re.match(locale_pattern, k) for k in obj)

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _is_valid_color(self, color: str) -> bool:
        """Validate color format (hex)."""
        pattern = r"^#[0-9a-fA-F]{6}$"
        return bool(re.match(pattern, color))

    def _is_valid_locale(self, locale: str) -> bool:
        """Validate locale format (en_US, tr_TR, etc)."""
        pattern = r"^[a-z]{2}_[A-Z]{2}$"
        return bool(re.match(pattern, locale))


def validate_spec(spec: dict) -> tuple[list[str], list[str]]:
    """
    Convenience function to validate a spec.

    Args:
        spec: Merged spec dict

    Returns:
        Tuple of (errors, warnings)
    """
    validator = SpecValidator(spec)
    return validator.validate()
