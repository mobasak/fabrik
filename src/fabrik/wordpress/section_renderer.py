"""
Fabrik WordPress Section Renderer

Renders section specs to WordPress Gutenberg blocks (HTML).

Tier 1 sections (10 types):
- hero
- cta / cta_banner
- features / features_grid
- services_grid
- testimonials
- faq
- contact_form
- rich_text / text_block
- logos_strip
- pricing_table (optional)
"""

from __future__ import annotations

from typing import Any


class SectionRenderer:
    """Render sections to WordPress blocks."""

    def __init__(self, spec: dict[str, Any], locale: str = "en_US"):
        """
        Initialize renderer.

        Args:
            spec: Full merged spec (for reference resolution)
            locale: Current locale for localized strings
        """
        self.spec: dict[str, Any] = spec
        self.locale = locale
        self.primary_locale = spec.get("languages", {}).get("primary", "en_US")

    def render_section(self, section: dict) -> str:
        """
        Render a single section to HTML.

        Args:
            section: Section spec dict

        Returns:
            HTML string (Gutenberg blocks)
        """
        section_type = section.get("type", "text_block")

        # Dispatch to type-specific renderer
        renderer_map = {
            "hero": self._render_hero,
            "cta": self._render_cta,
            "cta_banner": self._render_cta,
            "features": self._render_features,
            "features_grid": self._render_features,
            "services_grid": self._render_services_grid,
            "testimonials": self._render_testimonials,
            "faq": self._render_faq,
            "contact_form": self._render_contact_form,
            "rich_text": self._render_rich_text,
            "text_block": self._render_rich_text,
            "logos_strip": self._render_logos_strip,
            "pricing_table": self._render_pricing_table,
        }

        renderer = renderer_map.get(section_type, self._render_fallback)
        return renderer(section)

    def render_all(self, sections: list) -> str:
        """
        Render all sections for a page.

        Args:
            sections: List of section specs

        Returns:
            Combined HTML
        """
        return "\n\n".join(self.render_section(s) for s in sections)

    # ─────────────────────────────────────────────────────────────────────────
    # Section Renderers
    # ─────────────────────────────────────────────────────────────────────────

    def _render_hero(self, section: dict) -> str:
        """Render hero section."""
        headline = self._get_localized(section, "headline", section.get("headline_ref"))
        subheadline = self._get_localized(section, "subheadline")
        cta_text = self._get_localized(section, "cta_text")
        cta_url = section.get("cta_url", "#")

        html = f"""<!-- wp:cover {{"dimRatio":50}} -->
<div class="wp-block-cover">
    <div class="wp-block-cover__inner-container">
        <!-- wp:heading {{"level":1,"textAlign":"center"}} -->
        <h1 class="has-text-align-center">{headline}</h1>
        <!-- /wp:heading -->"""

        if subheadline:
            html += f"""
        <!-- wp:paragraph {{"align":"center"}} -->
        <p class="has-text-align-center">{subheadline}</p>
        <!-- /wp:paragraph -->"""

        if cta_text:
            html += f"""
        <!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
        <div class="wp-block-buttons">
            <!-- wp:button -->
            <div class="wp-block-button">
                <a class="wp-block-button__link" href="{cta_url}">{cta_text}</a>
            </div>
            <!-- /wp:button -->
        </div>
        <!-- /wp:buttons -->"""

        html += """
    </div>
</div>
<!-- /wp:cover -->"""

        return html

    def _render_cta(self, section: dict) -> str:
        """Render CTA section."""
        headline = self._get_localized(section, "headline")
        cta_text = self._get_localized(section, "cta_text")
        cta_url = section.get("cta_url", "#")

        return f"""<!-- wp:group {{"backgroundColor":"primary"}} -->
<div class="wp-block-group has-primary-background-color has-background">
    <!-- wp:heading {{"textAlign":"center"}} -->
    <h2 class="has-text-align-center">{headline}</h2>
    <!-- /wp:heading -->

    <!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
    <div class="wp-block-buttons">
        <!-- wp:button {{"backgroundColor":"accent"}} -->
        <div class="wp-block-button">
            <a class="wp-block-button__link has-accent-background-color" href="{cta_url}">{cta_text}</a>
        </div>
        <!-- /wp:button -->
    </div>
    <!-- /wp:buttons -->
</div>
<!-- /wp:group -->"""

    def _render_features(self, section: dict) -> str:
        """Render features grid."""
        headline = self._get_localized(section, "headline")
        columns = section.get("columns", 3)
        items = self._get_items(section)

        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline}</h2>
<!-- /wp:heading -->

<!-- wp:columns {{"align":"wide"}} -->
<div class="wp-block-columns alignwide">"""

        for item in items:
            icon = item.get("icon", "")
            title = self._get_localized_from_dict(item, "title")
            description = self._get_localized_from_dict(item, "description")

            html += f"""
    <!-- wp:column -->
    <div class="wp-block-column">
        <!-- wp:heading {{"level":3}} -->
        <h3>{title}</h3>
        <!-- /wp:heading -->

        <!-- wp:paragraph -->
        <p>{description}</p>
        <!-- /wp:paragraph -->
    </div>
    <!-- /wp:column -->"""

        html += """
</div>
<!-- /wp:columns -->"""

        return html

    def _render_services_grid(self, section: dict) -> str:
        """Render services grid."""
        headline = self._get_localized(section, "headline")
        source = section.get("source", "entities.services")
        columns = section.get("columns", 3)
        show_summary = section.get("show_summary", True)

        # Get services from spec
        services_data = self._resolve_ref(source) or []

        # Handle new entity config format: {items: [...], parent_page: "...", ...}
        if isinstance(services_data, dict):
            services = services_data.get("items", [])
        else:
            services = services_data

        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline}</h2>
<!-- /wp:heading -->

<!-- wp:columns {{"align":"wide"}} -->
<div class="wp-block-columns alignwide">"""

        for service in services:
            name = self._get_localized_from_dict(service, "name")
            summary = self._get_localized_from_dict(service, "summary") if show_summary else ""
            slug = service.get("slug", "")
            url = f"/services/{slug}/" if slug else "#"

            html += f"""
    <!-- wp:column -->
    <div class="wp-block-column">
        <!-- wp:heading {{"level":3}} -->
        <h3><a href="{url}">{name}</a></h3>
        <!-- /wp:heading -->"""

            if summary:
                html += f"""
        <!-- wp:paragraph -->
        <p>{summary}</p>
        <!-- /wp:paragraph -->"""

            html += """
    </div>
    <!-- /wp:column -->"""

        html += """
</div>
<!-- /wp:columns -->"""

        return html

    def _render_testimonials(self, section: dict) -> str:
        """Render testimonials."""
        headline = self._get_localized(section, "headline")
        items = self._get_items(section)

        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline}</h2>
<!-- /wp:heading -->

<!-- wp:columns -->
<div class="wp-block-columns">"""

        for item in items:
            quote = self._get_localized_from_dict(item, "quote")
            name = item.get("name", "")
            role = item.get("role", "")
            company = item.get("company", "")

            html += f"""
    <!-- wp:column -->
    <div class="wp-block-column">
        <!-- wp:quote -->
        <blockquote class="wp-block-quote">
            <p>{quote}</p>
            <cite>{name}{f", {role}" if role else ""}{f" at {company}" if company else ""}</cite>
        </blockquote>
        <!-- /wp:quote -->
    </div>
    <!-- /wp:column -->"""

        html += """
</div>
<!-- /wp:columns -->"""

        return html

    def _render_faq(self, section: dict) -> str:
        """Render FAQ section."""
        headline = self._get_localized(section, "headline")
        items = self._get_items(section)

        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline}</h2>
<!-- /wp:heading -->"""

        for item in items:
            question = self._get_localized_from_dict(item, "question")
            answer = self._get_localized_from_dict(item, "answer")

            html += f"""
<!-- wp:heading {{"level":3}} -->
<h3>{question}</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>{answer}</p>
<!-- /wp:paragraph -->"""

        return html

    def _render_contact_form(self, section: dict) -> str:
        """Render contact form placeholder."""
        headline = self._get_localized(section, "headline")
        show_info = section.get("show_info", True)

        # Note: Actual form will be created by FormCreator
        # This is just a placeholder
        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline or "Contact Us"}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>[Contact form will be inserted here]</p>
<!-- /wp:paragraph -->"""

        if show_info:
            contact = self.spec.get("contact", {})
            email = contact.get("email", "")

            html += f"""
<!-- wp:paragraph -->
<p><strong>Email:</strong> <a href="mailto:{email}">{email}</a></p>
<!-- /wp:paragraph -->"""

        return html

    def _render_rich_text(self, section: dict) -> str:
        """Render rich text / text block."""
        content = section.get("content")

        if not content:
            # Try content_ref
            content_ref = section.get("content_ref")
            if content_ref:
                content = self._resolve_ref(content_ref)

        if not content:
            content = ""

        # Simple paragraph wrapper
        return f"""<!-- wp:paragraph -->
<p>{content}</p>
<!-- /wp:paragraph -->"""

    def _render_logos_strip(self, section: dict) -> str:
        """Render logos strip."""
        headline = self._get_localized(section, "headline")
        items = section.get("items", [])

        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline}</h2>
<!-- /wp:heading -->

<!-- wp:gallery {{"linkTo":"none"}} -->
<figure class="wp-block-gallery">"""

        for item in items:
            image = item.get("image", "")
            alt = item.get("alt", "")

            html += f"""
    <figure class="wp-block-image">
        <img src="{image}" alt="{alt}"/>
    </figure>"""

        html += """
</figure>
<!-- /wp:gallery -->"""

        return html

    def _render_pricing_table(self, section: dict) -> str:
        """Render pricing table."""
        headline = self._get_localized(section, "headline")
        plans = section.get("plans", [])

        html = f"""<!-- wp:heading {{"textAlign":"center"}} -->
<h2 class="has-text-align-center">{headline}</h2>
<!-- /wp:heading -->

<!-- wp:columns -->
<div class="wp-block-columns">"""

        for plan in plans:
            name = self._get_localized_from_dict(plan, "name")
            price = plan.get("price", "")
            features = plan.get("features", [])

            html += f"""
    <!-- wp:column -->
    <div class="wp-block-column">
        <!-- wp:heading {{"level":3,"textAlign":"center"}} -->
        <h3 class="has-text-align-center">{name}</h3>
        <!-- /wp:heading -->

        <!-- wp:paragraph {{"align":"center"}} -->
        <p class="has-text-align-center"><strong>{price}</strong></p>
        <!-- /wp:paragraph -->

        <!-- wp:list -->
        <ul>"""

            for feature in features:
                html += f"<li>{feature}</li>"

            html += """</ul>
        <!-- /wp:list -->
    </div>
    <!-- /wp:column -->"""

        html += """
</div>
<!-- /wp:columns -->"""

        return html

    def _render_fallback(self, section: dict) -> str:
        """Fallback renderer for unknown section types."""
        section_type = section.get("type", "unknown")
        return f"""<!-- wp:paragraph -->
<p>[Section type '{section_type}' not yet implemented]</p>
<!-- /wp:paragraph -->"""

    # ─────────────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _get_localized(self, section: dict, key: str, ref: str | None = None) -> str:
        """Get localized string from section."""
        # Try direct key first
        value = section.get(key)

        # Try reference if provided
        if not value and ref:
            value = self._resolve_ref(ref)

        if not value:
            return ""

        # If it's a dict, extract locale
        if isinstance(value, dict):
            return value.get(self.locale) or value.get(self.primary_locale, "")

        return str(value)

    def _get_localized_from_dict(self, item: dict, key: str) -> str:
        """Get localized string from item dict."""
        value = item.get(key, "")

        if isinstance(value, dict):
            return value.get(self.locale) or value.get(self.primary_locale, "")

        return str(value)

    def _get_items(self, section: dict) -> list:
        """Get items from section (inline or ref)."""
        # Inline items override ref
        items = section.get("items")
        if items:
            return items

        # Try items_ref
        items_ref = section.get("items_ref")
        if items_ref:
            items = self._resolve_ref(items_ref)
            if items:
                return items

        return []

    def _resolve_ref(self, ref: str) -> Any:
        """Resolve reference path in spec."""
        keys = ref.split(".")
        value: Any = self.spec

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

            if value is None:
                return None

        return value


def render_sections(sections: list, spec: dict, locale: str = "en_US") -> str:
    """
    Convenience function to render sections.

    Args:
        sections: List of section specs
        spec: Full merged spec
        locale: Current locale

    Returns:
        Combined HTML
    """
    renderer = SectionRenderer(spec, locale)
    return renderer.render_all(sections)
