"""
WordPress Content Generator - Generate page content using Claude API.

Handles:
- AI-powered content generation for pages
- Section-based content building
- Multi-language content generation
"""

import os
from dataclasses import dataclass

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


@dataclass
class GeneratedContent:
    """Generated content result."""

    html: str
    title: str
    meta_description: str = ""
    word_count: int = 0


class ContentGenerator:
    """
    Generate WordPress page content using Claude API.

    Usage:
        generator = ContentGenerator()
        content = generator.generate_page(page_spec, brand, context)
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize content generator.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            model: Model to use (default: claude-sonnet-4-20250514)
        """
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package required: pip install anthropic")

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.model = model or self.DEFAULT_MODEL
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_page(
        self,
        page: dict,
        brand: dict,
        context: str = "",
        language: str = "en",
    ) -> GeneratedContent:
        """
        Generate content for a page.

        Args:
            page: Page spec with title, sections, etc.
            brand: Brand info (name, tagline, colors)
            context: Additional context about the business
            language: Output language code

        Returns:
            GeneratedContent with HTML and metadata
        """
        title = page.get("title", "Page")
        sections = page.get("sections", [])

        prompt = self._build_prompt(title, sections, brand, context, language)

        response = self.client.messages.create(
            model=self.model, max_tokens=4000, messages=[{"role": "user", "content": prompt}]
        )

        html = response.content[0].text

        # Extract word count
        import re

        text_only = re.sub(r"<[^>]+>", "", html)
        word_count = len(text_only.split())

        return GeneratedContent(
            html=html,
            title=title,
            word_count=word_count,
        )

    def _build_prompt(
        self,
        title: str,
        sections: list,
        brand: dict,
        context: str,
        language: str,
    ) -> str:
        """Build the generation prompt."""

        sections_desc = self._format_sections(sections)

        lang_instruction = ""
        if language != "en":
            lang_map = {"tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish"}
            lang_name = lang_map.get(language, language)
            lang_instruction = f"\n\nIMPORTANT: Generate all content in {lang_name}."

        return f"""Generate professional website content for a "{title}" page.

## Brand Information
- Company: {brand.get('name', 'Company')}
- Tagline: {brand.get('tagline', '')}
{f"- Context: {context}" if context else ""}

## Page Sections to Include
{sections_desc if sections_desc else "Create appropriate sections for this page type."}

## Requirements
1. Professional, confident tone
2. SEO-friendly structure with proper headings (H2, H3)
3. Clear value propositions
4. Call-to-action where appropriate
5. Output as clean HTML (no <html>, <head>, <body> tags)
6. Use semantic HTML elements
7. Keep paragraphs concise and scannable
8. Include bullet points where appropriate{lang_instruction}

## Output Format
Return ONLY the HTML content, no explanations or markdown code blocks."""

    def _format_sections(self, sections: list) -> str:
        """Format sections for the prompt."""
        if not sections:
            return ""

        formatted = []
        for i, section in enumerate(sections, 1):
            section_type = section.get("type", "text_block")

            desc = f"{i}. {section_type.replace('_', ' ').title()}"

            if headline := section.get("headline"):
                desc += f"\n   Headline: {headline}"
            if subheadline := section.get("subheadline"):
                desc += f"\n   Subheadline: {subheadline}"
            if content := section.get("content"):
                desc += f"\n   Content hint: {content[:100]}..."
            if items := section.get("items"):
                desc += f"\n   Items: {len(items)} items"

            formatted.append(desc)

        return "\n".join(formatted)

    def generate_service_page(
        self,
        service_name: str,
        service_items: list,
        brand: dict,
        language: str = "en",
    ) -> GeneratedContent:
        """
        Generate content for a service category page.

        Args:
            service_name: Name of the service category
            service_items: List of services in this category
            brand: Brand information
            language: Output language

        Returns:
            GeneratedContent
        """
        prompt = f"""Generate professional service page content for "{service_name}".

## Company
{brand.get('name', 'Company')} - {brand.get('tagline', '')}

## Services in this category
{chr(10).join(f"- {item}" for item in service_items)}

## Requirements
1. Brief intro paragraph explaining this service category
2. For each service, provide:
   - H3 heading
   - 2-3 sentence description
   - Key benefits (bullet points)
3. End with a call-to-action section
4. Professional B2B tone
5. Output as clean HTML only

{"Generate in Turkish." if language == "tr" else ""}"""

        response = self.client.messages.create(
            model=self.model, max_tokens=3000, messages=[{"role": "user", "content": prompt}]
        )

        return GeneratedContent(
            html=response.content[0].text,
            title=service_name,
        )

    def generate_homepage(self, spec: dict) -> GeneratedContent:
        """
        Generate homepage content from full site spec.

        Args:
            spec: Full site specification

        Returns:
            GeneratedContent for homepage
        """
        brand = spec.get("brand", {})
        homepage = None

        # Find homepage in pages
        for page in spec.get("pages", []):
            if page.get("slug") == "":
                homepage = page
                break

        if not homepage:
            homepage = {"title": "Home", "sections": []}

        # Build context from services
        services_context = ""
        for page in spec.get("pages", []):
            if page.get("slug") == "services":
                children = page.get("children", [])
                if children:
                    services_context = "Services: " + ", ".join(
                        c.get("title", "") for c in children
                    )
                break

        return self.generate_page(
            homepage,
            brand,
            context=services_context,
        )


def generate_content(
    page: dict,
    brand: dict,
    context: str = "",
    language: str = "en",
    api_key: str | None = None,
) -> GeneratedContent:
    """
    Convenience function to generate page content.

    Args:
        page: Page specification
        brand: Brand information
        context: Additional context
        language: Output language
        api_key: Optional API key

    Returns:
        GeneratedContent
    """
    generator = ContentGenerator(api_key=api_key)
    return generator.generate_page(page, brand, context, language)
