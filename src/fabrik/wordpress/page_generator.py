"""
Fabrik WordPress Page Generator

Generates pages from:
1. Preset page templates (explicit pages)
2. Entity data (services, features, products → pages)

Handles:
- Page hierarchy (parent/child)
- Slug conflicts (explicit wins)
- Section rendering
- Localization
"""

from fabrik.wordpress.section_renderer import SectionRenderer


class PageGenerator:
    """Generate pages from spec."""

    def __init__(self, spec: dict, locale: str = "en_US"):
        """
        Initialize page generator.

        Args:
            spec: Merged and normalized spec
            locale: Current locale
        """
        self.spec = spec
        self.locale = locale
        self.primary_locale = spec.get("languages", {}).get("primary", "en_US")
        self.renderer = SectionRenderer(spec, locale)

    def generate_all(self) -> list[dict]:
        """
        Generate all pages from spec.

        Returns:
            List of page specs ready for PageCreator
        """
        pages = []

        # 1. Get explicit pages from spec
        explicit_pages = self.spec.get("pages", [])
        if explicit_pages:
            pages.extend(self._process_explicit_pages(explicit_pages))

        # 2. Get pages from preset templates
        preset_pages = self._generate_from_templates()
        pages.extend(preset_pages)

        # 3. Generate entity pages
        entity_pages = self._generate_from_entities()
        pages.extend(entity_pages)

        # 4. Resolve conflicts (explicit wins)
        pages = self._resolve_conflicts(pages)

        return pages

    def _process_explicit_pages(self, pages: list) -> list[dict]:
        """Process explicit pages from spec."""
        processed = []

        for page in pages:
            processed_page = {
                "slug": page.get("slug", ""),
                "title": self._get_localized(page, "title"),
                "content": self._render_page_content(page),
                "status": page.get("status", "publish"),
                "template": page.get("template", ""),
                "source": "explicit",
            }

            # Handle children
            children = page.get("children", [])
            if children:
                processed_page["children"] = self._process_explicit_pages(children)

            processed.append(processed_page)

        return processed

    def _generate_from_templates(self) -> list[dict]:
        """Generate pages from preset page_templates."""
        pages = []
        templates = self.spec.get("page_templates", {})

        for template_name, template in templates.items():
            # Skip entity detail templates (used for generated pages)
            if template_name.endswith("-detail"):
                continue

            slug = template.get("slug", template_name)
            title = self._get_localized(template, "title")

            # Skip if no title (might be a template only)
            if not title:
                continue

            page = {
                "slug": slug,
                "title": title,
                "content": self._render_page_content(template),
                "status": "publish",
                "template": template.get("template", ""),
                "source": "preset_template",
            }

            pages.append(page)

        return pages

    def _generate_from_entities(self) -> list[dict]:
        """Generate pages from entities (services, features, products)."""
        pages = []
        entities = self.spec.get("entities", {})

        # Process each entity type
        entity_types = [
            ("services", "service-detail"),
            ("features", "feature-detail"),
            ("products", "product-detail"),
            ("locations", "location-detail"),
        ]

        for entity_key, default_template in entity_types:
            entity_config = entities.get(entity_key, {})

            # Skip if not enabled or no data
            if not entity_config:
                continue

            # Handle both dict (with config) and list (legacy)
            if isinstance(entity_config, dict):
                # New format: {items: [...], parent_page: "...", page_template: "..."}
                items = entity_config.get("items", [])
                parent_slug = entity_config.get("parent_page", entity_key)
                template_name = entity_config.get("page_template", default_template)

                # Check if generation is enabled
                if not entity_config.get("generate_pages", True):
                    continue
            else:
                # Legacy format: direct list
                items = entity_config if isinstance(entity_config, list) else []
                parent_slug = entity_key
                template_name = default_template

            # Generate pages for this entity type
            if items:
                entity_pages = self._generate_entity_pages(
                    items, parent_slug=parent_slug, template_name=template_name
                )
                pages.extend(entity_pages)

        return pages

    def _generate_entity_pages(
        self, entities: list, parent_slug: str, template_name: str
    ) -> list[dict]:
        """
        Generate pages from entity list.

        Returns pages with child slug only (no slashes) and parent_slug for hierarchy.
        The deployer will resolve parent_id and create proper parent-child relationships.
        """
        pages = []

        # Get entity detail template
        templates = self.spec.get("page_templates", {})
        detail_template = templates.get(template_name, {})

        for entity in entities:
            slug = entity.get("slug", "")
            if not slug:
                continue

            # Get entity name
            name = self._get_localized_from_dict(entity, "name")
            if not name:
                name = slug.replace("-", " ").title()

            # Render content from template
            content = self._render_entity_page(entity, detail_template)

            page = {
                "slug": slug,  # Child slug only (no slashes)
                "title": name,
                "content": content,
                "status": "publish",
                "template": detail_template.get("template", ""),
                "source": "entity",
                "entity_type": parent_slug,  # Parent slug for hierarchy resolution
                "parent_slug": parent_slug,  # Explicit parent reference
            }

            pages.append(page)

        return pages

    def _render_page_content(self, page: dict) -> str:
        """Render page content from sections."""
        sections = page.get("sections", [])
        if not sections:
            # Check for direct content
            content = page.get("content", "")
            if content:
                return content

            # Check for content_ref
            content_ref = page.get("content_ref")
            if content_ref:
                content = self._resolve_ref(content_ref)
                if content:
                    return content

            return ""

        # Render sections
        return self.renderer.render_all(sections)

    def _render_entity_page(self, entity: dict, template: dict) -> str:
        """Render entity page from template."""
        sections = template.get("sections", [])
        if not sections:
            # Fallback: render entity description
            description = self._get_localized_from_dict(entity, "description")
            if description:
                return f"<p>{description}</p>"
            return ""

        # Create entity-aware renderer
        # Replace entity.* references with actual entity data
        entity_sections = []
        for section in sections:
            section_copy = section.copy()

            # Replace entity.* refs
            for key, value in section_copy.items():
                if isinstance(value, str) and value.startswith("entity."):
                    # Resolve entity field
                    field = value.replace("entity.", "")
                    entity_value = entity.get(field, "")
                    section_copy[key] = entity_value

            entity_sections.append(section_copy)

        return self.renderer.render_all(entity_sections)

    def _resolve_conflicts(self, pages: list) -> list[dict]:
        """
        Resolve slug conflicts.

        Priority: explicit > preset_template > entity
        """
        seen = {}
        resolved = []

        # Sort by priority
        priority = {"explicit": 0, "preset_template": 1, "entity": 2}
        pages_sorted = sorted(pages, key=lambda p: priority.get(p.get("source", "entity"), 99))

        for page in pages_sorted:
            slug = page.get("slug", "")

            if slug in seen:
                # Conflict - skip lower priority
                continue

            seen[slug] = page.get("source")
            resolved.append(page)

        return resolved

    def _get_localized(self, obj: dict, key: str) -> str:
        """Get localized string from object."""
        value = obj.get(key, "")

        if isinstance(value, dict):
            return value.get(self.locale) or value.get(self.primary_locale, "")

        return str(value)

    def _get_localized_from_dict(self, obj: dict, key: str) -> str:
        """Get localized string from dict."""
        value = obj.get(key, "")

        if isinstance(value, dict):
            return value.get(self.locale) or value.get(self.primary_locale, "")

        return str(value)

    def _resolve_ref(self, ref: str) -> str | None:
        """Resolve reference path in spec."""
        keys = ref.split(".")
        value = self.spec

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

            if value is None:
                return None

        return str(value) if value else None


def generate_pages(spec: dict, locale: str = "en_US") -> list[dict]:
    """
    Convenience function to generate pages.

    Args:
        spec: Merged and normalized spec
        locale: Current locale

    Returns:
        List of page specs
    """
    generator = PageGenerator(spec, locale)
    return generator.generate_all()
