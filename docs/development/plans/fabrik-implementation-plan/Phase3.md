> **Phase Navigation:** [← Phase 2](Phase2.md) | **Phase 3** | [Phase 4 →](Phase4.md) | [All Phases](roadmap.md)

**Status:** ✅ COMPLETE (historical implementation)
## Phase 3: AI Content Integration — Complete Narrative

**Status: ❌ Not Started** (Requires Phase 2)

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | LLM client wrapper (Claude/OpenAI) | ❌ Pending |
| 2 | Content generation engine | ❌ Pending |
| 3 | Content revision system | ❌ Pending |
| 4 | Bulk generation tools | ❌ Pending |
| 5 | SEO optimization | ❌ Pending |
| 6 | Windsurf agent integration | ❌ Pending |

**Completion: 0/6 tasks (0%)**

---

### What We're Building in Phase 3

By the end of Phase 3, you will have:

1. **LLM client wrapper** that talks to Claude/OpenAI APIs
2. **Content generation engine** that creates pages and posts from prompts
3. **Content revision system** that modifies existing content based on instructions
4. **Bulk generation tools** for service pages, FAQs, blog series
5. **SEO optimization** with meta descriptions and title generation
6. **Windsurf agent integration** with context rules and capabilities
7. **Full AI-driven site creation** — from empty WordPress to populated site in one conversation

This transforms Fabrik from "operate WordPress programmatically" to "AI agents can build and manage complete websites autonomously."

---

### Prerequisites

Before starting Phase 3, confirm:

```
[ ] Phase 1 complete (Fabrik core working)
[ ] Phase 2 complete (WordPress automation working)
[ ] At least one WordPress site deployed with working REST API
[ ] Claude API key (from console.anthropic.com)
[ ] OpenAI API key (optional, for fallback/comparison)
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  WINDSURF AGENT                                                 │
│                                                                 │
│  "Create a professional website for ACME Corp, a B2B           │
│   manufacturing company. Include Home, About, Services,         │
│   and Contact pages."                                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  FABRIK AI LAYER                                                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Content Generator                                      │    │
│  │  • Prompt templates for different content types         │    │
│  │  • Industry/tone customization                          │    │
│  │  • SEO optimization                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Content Reviser                                        │    │
│  │  • Fetch existing content                               │    │
│  │  • Apply revision instructions                          │    │
│  │  • Preserve structure, update copy                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  LLM Client                                             │    │
│  │  • Claude API (primary)                                 │    │
│  │  • OpenAI API (fallback)                                │    │
│  │  • Rate limiting, retries, cost tracking                │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  WORDPRESS DRIVER (Phase 2)                                     │
│                                                                 │
│  • Create/update pages                                          │
│  • Create/update posts                                          │
│  • Upload media                                                 │
│  • Configure menus                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: LLM Client Wrapper

**Why:** We need a unified interface to talk to LLM APIs. This wrapper handles authentication, rate limiting, retries, and provides a consistent interface regardless of which model we're using.

**Code:**

```python
# compiler/ai/llm_client.py

import os
import time
import json
from typing import Optional, Union, Generator
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import httpx

class LLMProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"

@dataclass
class LLMResponse:
    content: str
    model: str
    provider: LLMProvider
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0

@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.CLAUDE
    model: Optional[str] = None  # Uses default if not specified
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120

# Token pricing (as of 2024, update as needed)
PRICING = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},  # per 1M tokens
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

DEFAULT_MODELS = {
    LLMProvider.CLAUDE: "claude-3-5-sonnet-20241022",
    LLMProvider.OPENAI: "gpt-4o",
}

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate(self, prompt: str, system: str = None, config: LLMConfig = None) -> LLMResponse:
        pass

    @abstractmethod
    def generate_stream(self, prompt: str, system: str = None, config: LLMConfig = None) -> Generator[str, None, None]:
        pass

class ClaudeClient(BaseLLMClient):
    """Anthropic Claude API client."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = httpx.Client(
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            timeout=120
        )

    def generate(self, prompt: str, system: str = None, config: LLMConfig = None) -> LLMResponse:
        config = config or LLMConfig()
        model = config.model or DEFAULT_MODELS[LLMProvider.CLAUDE]

        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": messages
        }

        if system:
            payload["system"] = system

        start = time.time()

        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.client.post(self.API_URL, json=payload)
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    continue
                raise

        latency = int((time.time() - start) * 1000)
        data = resp.json()

        content = data["content"][0]["text"]
        input_tokens = data["usage"]["input_tokens"]
        output_tokens = data["usage"]["output_tokens"]

        # Calculate cost
        pricing = PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.CLAUDE,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency
        )

    def generate_stream(self, prompt: str, system: str = None, config: LLMConfig = None) -> Generator[str, None, None]:
        """Stream response token by token."""
        config = config or LLMConfig()
        model = config.model or DEFAULT_MODELS[LLMProvider.CLAUDE]

        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": messages,
            "stream": True
        }

        if system:
            payload["system"] = system

        with self.client.stream("POST", self.API_URL, json=payload) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["type"] == "content_block_delta":
                        yield data["delta"].get("text", "")

class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=120
        )

    def generate(self, prompt: str, system: str = None, config: LLMConfig = None) -> LLMResponse:
        config = config or LLMConfig()
        model = config.model or DEFAULT_MODELS[LLMProvider.OPENAI]

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": messages
        }

        start = time.time()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.client.post(self.API_URL, json=payload)
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise

        latency = int((time.time() - start) * 1000)
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        input_tokens = data["usage"]["prompt_tokens"]
        output_tokens = data["usage"]["completion_tokens"]

        pricing = PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.OPENAI,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency
        )

    def generate_stream(self, prompt: str, system: str = None, config: LLMConfig = None) -> Generator[str, None, None]:
        config = config or LLMConfig()
        model = config.model or DEFAULT_MODELS[LLMProvider.OPENAI]

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": messages,
            "stream": True
        }

        with self.client.stream("POST", self.API_URL, json=payload) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    data = json.loads(line[6:])
                    delta = data["choices"][0]["delta"]
                    if "content" in delta:
                        yield delta["content"]

class LLMClient:
    """
    Unified LLM client with automatic fallback.

    Usage:
        client = LLMClient()
        response = client.generate("Write a blog post about AI")
        print(response.content)
    """

    def __init__(self, primary: LLMProvider = LLMProvider.CLAUDE):
        self.primary = primary
        self._clients = {}

        # Initialize available clients
        try:
            self._clients[LLMProvider.CLAUDE] = ClaudeClient()
        except ValueError:
            pass

        try:
            self._clients[LLMProvider.OPENAI] = OpenAIClient()
        except ValueError:
            pass

        if not self._clients:
            raise ValueError("No LLM API keys configured")

    def generate(
        self,
        prompt: str,
        system: str = None,
        config: LLMConfig = None,
        fallback: bool = True
    ) -> LLMResponse:
        """
        Generate content with optional fallback.

        Args:
            prompt: User prompt
            system: System prompt
            config: LLM configuration
            fallback: If True, try other provider on failure
        """
        config = config or LLMConfig(provider=self.primary)

        # Try primary
        if config.provider in self._clients:
            try:
                return self._clients[config.provider].generate(prompt, system, config)
            except Exception as e:
                if not fallback:
                    raise
                print(f"Primary LLM failed: {e}, trying fallback...")

        # Try fallback
        for provider, client in self._clients.items():
            if provider != config.provider:
                try:
                    return client.generate(prompt, system, config)
                except Exception:
                    continue

        raise RuntimeError("All LLM providers failed")

    def generate_stream(
        self,
        prompt: str,
        system: str = None,
        config: LLMConfig = None
    ) -> Generator[str, None, None]:
        """Stream response."""
        config = config or LLMConfig(provider=self.primary)

        if config.provider in self._clients:
            yield from self._clients[config.provider].generate_stream(prompt, system, config)
        else:
            # Use first available client
            for client in self._clients.values():
                yield from client.generate_stream(prompt, system, config)
                return

# Convenience function
def get_llm_client() -> LLMClient:
    """Get configured LLM client."""
    return LLMClient()
```

**Test:**

```bash
cd ~/projects/fabrik
source secrets/platform.env

python3 << 'EOF'
from compiler.ai.llm_client import LLMClient

client = LLMClient()
response = client.generate(
    "Write a one-paragraph description of a fictional tech company.",
    system="You are a professional copywriter."
)

print(f"Content: {response.content[:200]}...")
print(f"Model: {response.model}")
print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")
print(f"Cost: ${response.cost_usd:.4f}")
EOF
```

**Time:** 2 hours

---

### Step 2: Page Generation from Prompts

**Why:** The core capability — take a description of what page you want and generate professional HTML content suitable for WordPress.

**Code:**

```python
# compiler/ai/content_generator.py

from typing import Optional
from dataclasses import dataclass
from enum import Enum

from compiler.ai.llm_client import LLMClient, LLMConfig

class PageType(str, Enum):
    HOME = "home"
    ABOUT = "about"
    SERVICES = "services"
    SERVICE_DETAIL = "service_detail"
    CONTACT = "contact"
    FAQ = "faq"
    BLOG_POST = "blog_post"
    LANDING = "landing"
    PRODUCT = "product"
    TEAM = "team"
    TESTIMONIALS = "testimonials"
    PRICING = "pricing"
    CUSTOM = "custom"

class Tone(str, Enum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    CASUAL = "casual"
    FORMAL = "formal"
    PERSUASIVE = "persuasive"

@dataclass
class ContentRequest:
    page_type: PageType
    title: str
    business_name: str
    business_description: str
    industry: Optional[str] = None
    tone: Tone = Tone.PROFESSIONAL
    target_audience: Optional[str] = None
    key_points: Optional[list[str]] = None
    call_to_action: Optional[str] = None
    word_count: int = 500
    include_sections: Optional[list[str]] = None
    additional_instructions: Optional[str] = None

@dataclass
class GeneratedContent:
    title: str
    html_content: str
    meta_description: str
    meta_title: str
    excerpt: Optional[str] = None
    suggested_slug: str = ""

class ContentGenerator:
    """Generate WordPress page/post content using LLMs."""

    SYSTEM_PROMPT = """You are an expert web content writer and copywriter. You create professional, engaging website content that converts visitors into customers.

Your content should:
- Be well-structured with clear headings (use HTML h2, h3 tags)
- Include compelling calls to action
- Be SEO-friendly with natural keyword usage
- Use short paragraphs and bullet points for readability
- Be professional yet approachable
- Include relevant details that build trust

Output format:
- Return ONLY the HTML content for the page body
- Use semantic HTML (h2, h3, p, ul, li, strong, em)
- Do not include <html>, <head>, <body>, or <article> wrapper tags
- Do not include inline styles unless specifically requested
- Use WordPress-compatible HTML that works with any theme"""

    def __init__(self):
        self.llm = LLMClient()

    def generate_page(self, request: ContentRequest) -> GeneratedContent:
        """Generate a complete page based on the request."""

        prompt = self._build_prompt(request)

        # Generate main content
        response = self.llm.generate(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            config=LLMConfig(temperature=0.7, max_tokens=4096)
        )

        html_content = self._clean_html(response.content)

        # Generate SEO metadata
        meta = self._generate_meta(request, html_content)

        # Generate slug
        slug = self._generate_slug(request.title)

        return GeneratedContent(
            title=request.title,
            html_content=html_content,
            meta_description=meta["description"],
            meta_title=meta["title"],
            excerpt=meta.get("excerpt"),
            suggested_slug=slug
        )

    def _build_prompt(self, request: ContentRequest) -> str:
        """Build the generation prompt based on request."""

        prompt_parts = []

        # Base instruction
        prompt_parts.append(f"Create content for a {request.page_type.value} page.")
        prompt_parts.append(f"Page title: {request.title}")
        prompt_parts.append(f"Business: {request.business_name}")
        prompt_parts.append(f"Business description: {request.business_description}")

        if request.industry:
            prompt_parts.append(f"Industry: {request.industry}")

        prompt_parts.append(f"Tone: {request.tone.value}")

        if request.target_audience:
            prompt_parts.append(f"Target audience: {request.target_audience}")

        if request.key_points:
            prompt_parts.append(f"Key points to include:")
            for point in request.key_points:
                prompt_parts.append(f"  - {point}")

        if request.call_to_action:
            prompt_parts.append(f"Call to action: {request.call_to_action}")

        prompt_parts.append(f"Target word count: approximately {request.word_count} words")

        # Page-type specific instructions
        type_instructions = self._get_type_instructions(request.page_type)
        if type_instructions:
            prompt_parts.append(f"\nPage-specific requirements:\n{type_instructions}")

        if request.include_sections:
            prompt_parts.append(f"\nMust include these sections:")
            for section in request.include_sections:
                prompt_parts.append(f"  - {section}")

        if request.additional_instructions:
            prompt_parts.append(f"\nAdditional instructions: {request.additional_instructions}")

        return "\n".join(prompt_parts)

    def _get_type_instructions(self, page_type: PageType) -> str:
        """Get specific instructions for each page type."""

        instructions = {
            PageType.HOME: """
- Start with a compelling hero section (headline + subheadline)
- Include a brief value proposition
- Highlight 3-4 key benefits or services
- Include social proof section (testimonials or trust indicators)
- End with a clear call to action""",

            PageType.ABOUT: """
- Tell the company story (origin, mission, values)
- Introduce the team or founder
- Highlight what makes the company unique
- Include company achievements or milestones
- End with why customers should trust this company""",

            PageType.SERVICES: """
- Brief overview of all services offered
- Individual sections for each main service
- Benefits of each service (not just features)
- Who each service is best suited for
- Call to action for getting started""",

            PageType.SERVICE_DETAIL: """
- Detailed explanation of the specific service
- Process or methodology
- Benefits and outcomes
- Pricing information or "contact for quote"
- FAQ section (3-4 common questions)
- Related services
- Call to action""",

            PageType.CONTACT: """
- Brief welcoming message
- Multiple contact methods (phone, email, address)
- Business hours if applicable
- What to expect after contact (response time)
- Simple contact form description
- Map or directions if relevant""",

            PageType.FAQ: """
- Organize questions by category if many
- Start with most common questions
- Provide clear, concise answers
- Link to relevant pages where appropriate
- Include contact info for questions not covered""",

            PageType.BLOG_POST: """
- Engaging introduction that hooks the reader
- Well-structured body with subheadings
- Practical, actionable information
- Examples or case studies where relevant
- Conclusion with key takeaways
- Call to action (subscribe, contact, read more)""",

            PageType.LANDING: """
- Single focused message/offer
- Compelling headline and subheadline
- Clear value proposition
- Benefits (not features)
- Social proof
- Single, prominent call to action
- Minimal distractions""",

            PageType.PRICING: """
- Clear pricing tiers or options
- What's included in each tier
- Comparison if multiple tiers
- FAQ about pricing
- Money-back guarantee or trial info
- Call to action for each tier""",

            PageType.TEAM: """
- Brief team overview
- Individual bios with photo placeholders
- Relevant experience and expertise
- Personal touch (interests, fun facts)
- Contact or connect options""",

            PageType.TESTIMONIALS: """
- Featured testimonials with names/companies
- Variety of customer types/industries
- Specific results or outcomes mentioned
- Star ratings if applicable
- Call to action to become a customer""",
        }

        return instructions.get(page_type, "")

    def _generate_meta(self, request: ContentRequest, content: str) -> dict:
        """Generate SEO metadata for the content."""

        prompt = f"""Based on this page content, generate SEO metadata.

Page title: {request.title}
Business: {request.business_name}
Content preview: {content[:500]}...

Generate:
1. Meta title (50-60 characters, include business name)
2. Meta description (150-160 characters, compelling, include call to action)
3. Excerpt (2-3 sentences for previews)

Format your response as:
META_TITLE: [your title]
META_DESCRIPTION: [your description]
EXCERPT: [your excerpt]"""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.5, max_tokens=500)
        )

        # Parse response
        meta = {"title": "", "description": "", "excerpt": ""}

        for line in response.content.split("\n"):
            if line.startswith("META_TITLE:"):
                meta["title"] = line.replace("META_TITLE:", "").strip()
            elif line.startswith("META_DESCRIPTION:"):
                meta["description"] = line.replace("META_DESCRIPTION:", "").strip()
            elif line.startswith("EXCERPT:"):
                meta["excerpt"] = line.replace("EXCERPT:", "").strip()

        # Fallbacks
        if not meta["title"]:
            meta["title"] = f"{request.title} | {request.business_name}"
        if not meta["description"]:
            meta["description"] = f"Learn about {request.title.lower()} from {request.business_name}."

        return meta

    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title."""
        import re
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        return slug

    def _clean_html(self, content: str) -> str:
        """Clean and normalize generated HTML."""
        import re

        # Remove markdown code blocks if present
        content = re.sub(r'^```html?\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

        # Remove wrapper tags if present
        content = re.sub(r'^<article[^>]*>', '', content)
        content = re.sub(r'</article>$', '', content)

        # Normalize whitespace
        content = content.strip()

        return content
```

**Time:** 2 hours

---

### Step 3: Post Generation from Prompts

**Why:** Blog posts have different requirements than pages — they need categories, tags, and are typically more conversational.

**Code:**

```python
# compiler/ai/blog_generator.py

from typing import Optional
from dataclasses import dataclass

from compiler.ai.llm_client import LLMClient, LLMConfig
from compiler.ai.content_generator import Tone

@dataclass
class BlogPostRequest:
    topic: str
    business_name: str
    industry: Optional[str] = None
    tone: Tone = Tone.PROFESSIONAL
    target_audience: Optional[str] = None
    keywords: Optional[list[str]] = None
    word_count: int = 1000
    include_intro: bool = True
    include_conclusion: bool = True
    include_cta: bool = True
    cta_text: Optional[str] = None
    additional_instructions: Optional[str] = None

@dataclass
class GeneratedBlogPost:
    title: str
    html_content: str
    meta_description: str
    excerpt: str
    suggested_slug: str
    suggested_categories: list[str]
    suggested_tags: list[str]

class BlogGenerator:
    """Generate blog posts using LLMs."""

    SYSTEM_PROMPT = """You are an expert blog content writer. You create engaging, informative blog posts that provide real value to readers while supporting business goals.

Your blog posts should:
- Have a compelling title that drives clicks
- Start with a hook that captures attention
- Use subheadings (h2, h3) to organize content
- Include practical, actionable information
- Use examples, statistics, or case studies when relevant
- Be conversational yet professional
- Include internal linking opportunities (marked with [LINK: topic])
- End with a clear takeaway and call to action

Output format:
- Return ONLY the HTML content
- Use semantic HTML (h2, h3, p, ul, li, blockquote, strong, em)
- Do not include wrapper tags
- Mark suggested internal links as [LINK: topic to link]"""

    def __init__(self):
        self.llm = LLMClient()

    def generate_post(self, request: BlogPostRequest) -> GeneratedBlogPost:
        """Generate a complete blog post."""

        # Generate title options first
        title = self._generate_title(request)

        # Generate main content
        prompt = self._build_prompt(request, title)

        response = self.llm.generate(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            config=LLMConfig(temperature=0.7, max_tokens=4096)
        )

        html_content = self._clean_html(response.content)

        # Generate metadata and taxonomies
        meta = self._generate_meta(request, title, html_content)
        taxonomies = self._suggest_taxonomies(request, title, html_content)

        return GeneratedBlogPost(
            title=title,
            html_content=html_content,
            meta_description=meta["description"],
            excerpt=meta["excerpt"],
            suggested_slug=self._generate_slug(title),
            suggested_categories=taxonomies["categories"],
            suggested_tags=taxonomies["tags"]
        )

    def _generate_title(self, request: BlogPostRequest) -> str:
        """Generate compelling blog title."""

        prompt = f"""Generate 1 compelling blog post title for this topic:

Topic: {request.topic}
Industry: {request.industry or "general"}
Target audience: {request.target_audience or "general readers"}

Requirements:
- Attention-grabbing but not clickbait
- 50-70 characters ideal
- Include benefit or intrigue
- Natural, not keyword-stuffed

Return ONLY the title, nothing else."""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.8, max_tokens=100)
        )

        return response.content.strip().strip('"')

    def _build_prompt(self, request: BlogPostRequest, title: str) -> str:
        """Build the generation prompt."""

        prompt_parts = [
            f"Write a blog post with this title: {title}",
            f"Topic: {request.topic}",
            f"Business/Author: {request.business_name}",
            f"Tone: {request.tone.value}",
            f"Target word count: {request.word_count} words",
        ]

        if request.industry:
            prompt_parts.append(f"Industry context: {request.industry}")

        if request.target_audience:
            prompt_parts.append(f"Target audience: {request.target_audience}")

        if request.keywords:
            prompt_parts.append(f"Keywords to naturally include: {', '.join(request.keywords)}")

        structure = []
        if request.include_intro:
            structure.append("- Engaging introduction that hooks the reader")
        structure.append("- Well-organized body with 3-5 main sections")
        if request.include_conclusion:
            structure.append("- Conclusion with key takeaways")
        if request.include_cta:
            cta = request.cta_text or "Contact us to learn more"
            structure.append(f"- Call to action: {cta}")

        prompt_parts.append(f"\nStructure:\n" + "\n".join(structure))

        if request.additional_instructions:
            prompt_parts.append(f"\nAdditional instructions: {request.additional_instructions}")

        return "\n".join(prompt_parts)

    def _generate_meta(self, request: BlogPostRequest, title: str, content: str) -> dict:
        """Generate SEO metadata."""

        prompt = f"""Generate SEO metadata for this blog post.

Title: {title}
Content preview: {content[:500]}...

Generate:
1. Meta description (150-160 chars, compelling, include benefit)
2. Excerpt (2-3 sentences for post previews/social sharing)

Format:
META_DESCRIPTION: [description]
EXCERPT: [excerpt]"""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.5, max_tokens=300)
        )

        meta = {"description": "", "excerpt": ""}

        for line in response.content.split("\n"):
            if line.startswith("META_DESCRIPTION:"):
                meta["description"] = line.replace("META_DESCRIPTION:", "").strip()
            elif line.startswith("EXCERPT:"):
                meta["excerpt"] = line.replace("EXCERPT:", "").strip()

        return meta

    def _suggest_taxonomies(self, request: BlogPostRequest, title: str, content: str) -> dict:
        """Suggest categories and tags."""

        prompt = f"""Suggest categories and tags for this blog post.

Title: {title}
Topic: {request.topic}
Industry: {request.industry or "general"}
Content preview: {content[:300]}...

Suggest:
- 1-2 categories (broad topics)
- 3-5 tags (specific keywords)

Format:
CATEGORIES: category1, category2
TAGS: tag1, tag2, tag3, tag4, tag5"""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.3, max_tokens=200)
        )

        taxonomies = {"categories": [], "tags": []}

        for line in response.content.split("\n"):
            if line.startswith("CATEGORIES:"):
                cats = line.replace("CATEGORIES:", "").strip()
                taxonomies["categories"] = [c.strip() for c in cats.split(",")]
            elif line.startswith("TAGS:"):
                tags = line.replace("TAGS:", "").strip()
                taxonomies["tags"] = [t.strip() for t in tags.split(",")]

        return taxonomies

    def _generate_slug(self, title: str) -> str:
        """Generate URL slug."""
        import re
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')[:60]

    def _clean_html(self, content: str) -> str:
        """Clean generated HTML."""
        import re
        content = re.sub(r'^```html?\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        return content.strip()
```

**Time:** 2 hours

---

### Step 4: SEO Meta Generation

**Why:** Every page and post needs SEO metadata. This is already partially implemented in Steps 2-3, but we'll add a dedicated utility for updating existing content.

**Code:**

```python
# compiler/ai/seo.py

from typing import Optional
from dataclasses import dataclass

from compiler.ai.llm_client import LLMClient, LLMConfig

@dataclass
class SEOContent:
    meta_title: str
    meta_description: str
    focus_keyword: Optional[str] = None
    secondary_keywords: list[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None

class SEOGenerator:
    """Generate SEO metadata and optimize content."""

    def __init__(self):
        self.llm = LLMClient()

    def generate_meta(
        self,
        title: str,
        content: str,
        business_name: str,
        target_keyword: Optional[str] = None
    ) -> SEOContent:
        """Generate SEO metadata for existing content."""

        prompt = f"""Analyze this content and generate SEO metadata.

Title: {title}
Business: {business_name}
Target keyword: {target_keyword or "determine from content"}

Content:
{content[:1500]}

Generate:
1. Meta title (50-60 chars, include brand name at end)
2. Meta description (150-160 chars, include CTA, compelling)
3. Focus keyword (main keyword to target)
4. Secondary keywords (3-5 related terms)
5. Open Graph title (for social sharing, can be same as meta title)
6. Open Graph description (for social sharing, slightly more casual)

Format:
META_TITLE: [title]
META_DESCRIPTION: [description]
FOCUS_KEYWORD: [keyword]
SECONDARY_KEYWORDS: [kw1, kw2, kw3]
OG_TITLE: [title]
OG_DESCRIPTION: [description]"""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.4, max_tokens=500)
        )

        # Parse response
        seo = SEOContent(
            meta_title="",
            meta_description="",
            secondary_keywords=[]
        )

        for line in response.content.split("\n"):
            if line.startswith("META_TITLE:"):
                seo.meta_title = line.split(":", 1)[1].strip()
            elif line.startswith("META_DESCRIPTION:"):
                seo.meta_description = line.split(":", 1)[1].strip()
            elif line.startswith("FOCUS_KEYWORD:"):
                seo.focus_keyword = line.split(":", 1)[1].strip()
            elif line.startswith("SECONDARY_KEYWORDS:"):
                kws = line.split(":", 1)[1].strip()
                seo.secondary_keywords = [k.strip() for k in kws.split(",")]
            elif line.startswith("OG_TITLE:"):
                seo.og_title = line.split(":", 1)[1].strip()
            elif line.startswith("OG_DESCRIPTION:"):
                seo.og_description = line.split(":", 1)[1].strip()

        return seo

    def optimize_content(
        self,
        content: str,
        target_keyword: str,
        current_score: Optional[int] = None
    ) -> str:
        """Suggest SEO improvements for content."""

        prompt = f"""Analyze this content for SEO and suggest improvements.

Target keyword: {target_keyword}
{f"Current SEO score: {current_score}/100" if current_score else ""}

Content:
{content[:2000]}

Analyze and provide:
1. Keyword usage (is target keyword in first paragraph, headings?)
2. Heading structure (proper h2/h3 hierarchy?)
3. Content length assessment
4. Readability issues
5. Internal linking opportunities
6. Specific improvement suggestions

Be concise and actionable."""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.4, max_tokens=800)
        )

        return response.content
```

**Time:** 1 hour

---

### Step 5: Content Revision System

**Why:** Often you don't need to generate new content — you need to modify existing content based on feedback. This is the "make it more professional" or "add a section about X" capability.

**Code:**

```python
# compiler/ai/content_reviser.py

from typing import Optional
from dataclasses import dataclass
from enum import Enum

from compiler.ai.llm_client import LLMClient, LLMConfig

class RevisionType(str, Enum):
    REWRITE = "rewrite"           # Complete rewrite
    IMPROVE = "improve"           # Improve quality
    EXPAND = "expand"             # Add more content
    SHORTEN = "shorten"           # Reduce length
    TONE_CHANGE = "tone_change"   # Change tone
    ADD_SECTION = "add_section"   # Add specific section
    UPDATE_INFO = "update_info"   # Update specific info
    FIX_ISSUES = "fix_issues"     # Fix specific problems
    CUSTOM = "custom"             # Custom instructions

@dataclass
class RevisionRequest:
    current_content: str
    revision_type: RevisionType
    instructions: str
    preserve_structure: bool = True
    preserve_links: bool = True
    target_length: Optional[int] = None

@dataclass
class RevisionResult:
    revised_content: str
    changes_summary: str
    original_length: int
    revised_length: int

class ContentReviser:
    """Revise existing content based on instructions."""

    SYSTEM_PROMPT = """You are an expert content editor. You revise and improve existing content while maintaining its core message and structure unless specifically asked to change it.

When revising:
- Preserve the overall structure unless asked to change it
- Maintain any internal links (marked with href or [LINK:])
- Keep SEO-relevant keywords
- Improve clarity and engagement
- Fix grammatical issues
- Ensure consistent tone throughout

Output format:
- Return the revised HTML content only
- Preserve all HTML tags from original
- Do not add wrapper tags"""

    def __init__(self):
        self.llm = LLMClient()

    def revise(self, request: RevisionRequest) -> RevisionResult:
        """Revise content based on request."""

        prompt = self._build_revision_prompt(request)

        response = self.llm.generate(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            config=LLMConfig(temperature=0.6, max_tokens=4096)
        )

        revised_content = self._clean_html(response.content)

        # Generate summary of changes
        summary = self._summarize_changes(request.current_content, revised_content)

        return RevisionResult(
            revised_content=revised_content,
            changes_summary=summary,
            original_length=len(request.current_content.split()),
            revised_length=len(revised_content.split())
        )

    def _build_revision_prompt(self, request: RevisionRequest) -> str:
        """Build the revision prompt."""

        prompt_parts = [
            f"Revise the following content.",
            f"\nRevision type: {request.revision_type.value}",
            f"Instructions: {request.instructions}",
        ]

        if request.preserve_structure:
            prompt_parts.append("Preserve the overall structure and section headings.")

        if request.preserve_links:
            prompt_parts.append("Preserve all links and link text.")

        if request.target_length:
            prompt_parts.append(f"Target length: approximately {request.target_length} words.")

        # Type-specific instructions
        if request.revision_type == RevisionType.EXPAND:
            prompt_parts.append("Add more detail, examples, and depth to existing sections.")
        elif request.revision_type == RevisionType.SHORTEN:
            prompt_parts.append("Remove redundancy, tighten prose, keep only essential information.")
        elif request.revision_type == RevisionType.TONE_CHANGE:
            prompt_parts.append("Adjust the tone throughout while keeping the same information.")
        elif request.revision_type == RevisionType.ADD_SECTION:
            prompt_parts.append("Add the new section in an appropriate location within the content.")

        prompt_parts.append(f"\nCurrent content:\n{request.current_content}")

        return "\n".join(prompt_parts)

    def _summarize_changes(self, original: str, revised: str) -> str:
        """Generate summary of changes made."""

        prompt = f"""Briefly summarize the changes made between these two versions.

Original (first 500 chars):
{original[:500]}

Revised (first 500 chars):
{revised[:500]}

List 3-5 key changes in bullet points. Be specific and concise."""

        response = self.llm.generate(
            prompt=prompt,
            config=LLMConfig(temperature=0.3, max_tokens=300)
        )

        return response.content

    def _clean_html(self, content: str) -> str:
        """Clean revised HTML."""
        import re
        content = re.sub(r'^```html?\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        return content.strip()

    # ─────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────

    def make_more_professional(self, content: str) -> RevisionResult:
        """Make content more professional in tone."""
        return self.revise(RevisionRequest(
            current_content=content,
            revision_type=RevisionType.TONE_CHANGE,
            instructions="Make the tone more professional and business-appropriate. Remove casual language, improve vocabulary, add credibility markers."
        ))

    def make_more_friendly(self, content: str) -> RevisionResult:
        """Make content more friendly and approachable."""
        return self.revise(RevisionRequest(
            current_content=content,
            revision_type=RevisionType.TONE_CHANGE,
            instructions="Make the tone warmer and more approachable. Use conversational language, add personality, maintain professionalism but be less formal."
        ))

    def expand_content(self, content: str, target_words: int = None) -> RevisionResult:
        """Expand content with more detail."""
        return self.revise(RevisionRequest(
            current_content=content,
            revision_type=RevisionType.EXPAND,
            instructions="Expand this content with more detail, examples, and supporting information.",
            target_length=target_words
        ))

    def shorten_content(self, content: str, target_words: int = None) -> RevisionResult:
        """Shorten content while keeping key information."""
        return self.revise(RevisionRequest(
            current_content=content,
            revision_type=RevisionType.SHORTEN,
            instructions="Shorten this content by removing redundancy and unnecessary detail. Keep all essential information and key messages.",
            target_length=target_words
        ))

    def add_section(self, content: str, section_topic: str, placement: str = "end") -> RevisionResult:
        """Add a new section to content."""
        return self.revise(RevisionRequest(
            current_content=content,
            revision_type=RevisionType.ADD_SECTION,
            instructions=f"Add a new section about: {section_topic}. Place it {placement} of the content.",
            preserve_structure=True
        ))

    def fix_and_improve(self, content: str, issues: list[str]) -> RevisionResult:
        """Fix specific issues in content."""
        issues_text = "\n".join(f"- {issue}" for issue in issues)
        return self.revise(RevisionRequest(
            current_content=content,
            revision_type=RevisionType.FIX_ISSUES,
            instructions=f"Fix these specific issues:\n{issues_text}"
        ))
```

**Time:** 2 hours

---

### Step 6-8: Bulk Generation Tools

**Why:** Often you need to generate multiple pieces of content at once — all service pages, a series of blog posts, FAQ sections, etc.

**Code:**

```python
# compiler/ai/bulk_generator.py

from typing import Optional, Callable
from dataclasses import dataclass
import time

from compiler.ai.content_generator import ContentGenerator, ContentRequest, PageType, Tone, GeneratedContent
from compiler.ai.blog_generator import BlogGenerator, BlogPostRequest, GeneratedBlogPost

@dataclass
class BulkGenerationResult:
    total: int
    successful: int
    failed: int
    results: list
    errors: list[str]
    total_cost_usd: float
    total_time_seconds: float

class BulkGenerator:
    """Generate multiple pieces of content efficiently."""

    def __init__(self):
        self.page_generator = ContentGenerator()
        self.blog_generator = BlogGenerator()

    def generate_service_pages(
        self,
        services: list[str],
        business_name: str,
        business_description: str,
        industry: str = None,
        tone: Tone = Tone.PROFESSIONAL,
        on_progress: Callable[[int, int, str], None] = None
    ) -> BulkGenerationResult:
        """
        Generate pages for multiple services.

        Args:
            services: List of service names
            business_name: Company name
            business_description: What the company does
            industry: Industry context
            tone: Writing tone
            on_progress: Callback(current, total, service_name)
        """

        results = []
        errors = []
        total_cost = 0.0
        start_time = time.time()

        for i, service in enumerate(services):
            if on_progress:
                on_progress(i + 1, len(services), service)

            try:
                request = ContentRequest(
                    page_type=PageType.SERVICE_DETAIL,
                    title=service,
                    business_name=business_name,
                    business_description=business_description,
                    industry=industry,
                    tone=tone,
                    word_count=600,
                    call_to_action=f"Contact us to learn more about our {service.lower()} services."
                )

                content = self.page_generator.generate_page(request)
                results.append({
                    "service": service,
                    "content": content,
                    "status": "success"
                })

            except Exception as e:
                errors.append(f"{service}: {str(e)}")
                results.append({
                    "service": service,
                    "content": None,
                    "status": "failed",
                    "error": str(e)
                })

            # Rate limiting - don't hammer the API
            time.sleep(1)

        return BulkGenerationResult(
            total=len(services),
            successful=len([r for r in results if r["status"] == "success"]),
            failed=len(errors),
            results=results,
            errors=errors,
            total_cost_usd=total_cost,
            total_time_seconds=time.time() - start_time
        )

    def generate_faq_page(
        self,
        questions: list[str],
        business_name: str,
        business_description: str,
        industry: str = None
    ) -> GeneratedContent:
        """Generate FAQ page from list of questions."""

        # Build FAQ content request
        faq_items = "\n".join(f"- {q}" for q in questions)

        request = ContentRequest(
            page_type=PageType.FAQ,
            title="Frequently Asked Questions",
            business_name=business_name,
            business_description=business_description,
            industry=industry,
            tone=Tone.FRIENDLY,
            additional_instructions=f"""
Answer these specific questions:
{faq_items}

Format each Q&A with:
- Question as h3 heading
- Clear, helpful answer
- Include relevant details
"""
        )

        return self.page_generator.generate_page(request)

    def generate_blog_series(
        self,
        topics: list[str],
        series_name: str,
        business_name: str,
        industry: str = None,
        tone: Tone = Tone.PROFESSIONAL,
        on_progress: Callable[[int, int, str], None] = None
    ) -> BulkGenerationResult:
        """Generate a series of related blog posts."""

        results = []
        errors = []
        start_time = time.time()

        for i, topic in enumerate(topics):
            if on_progress:
                on_progress(i + 1, len(topics), topic)

            try:
                request = BlogPostRequest(
                    topic=topic,
                    business_name=business_name,
                    industry=industry,
                    tone=tone,
                    word_count=1000,
                    additional_instructions=f"This is part of a blog series called '{series_name}'. Reference other posts in the series where relevant."
                )

                post = self.blog_generator.generate_post(request)
                results.append({
                    "topic": topic,
                    "post": post,
                    "status": "success"
                })

            except Exception as e:
                errors.append(f"{topic}: {str(e)}")
                results.append({
                    "topic": topic,
                    "post": None,
                    "status": "failed",
                    "error": str(e)
                })

            time.sleep(1)

        return BulkGenerationResult(
            total=len(topics),
            successful=len([r for r in results if r["status"] == "success"]),
            failed=len(errors),
            results=results,
            errors=errors,
            total_cost_usd=0,
            total_time_seconds=time.time() - start_time
        )

    def generate_website_content(
        self,
        business_name: str,
        business_description: str,
        industry: str,
        services: list[str],
        tone: Tone = Tone.PROFESSIONAL,
        include_blog: bool = False,
        blog_topics: list[str] = None,
        on_progress: Callable[[str, int, int], None] = None
    ) -> dict:
        """
        Generate complete website content package.

        Returns dict with:
        - pages: dict of page content
        - posts: list of blog posts (if include_blog)
        - menus: suggested menu structure
        """

        results = {
            "pages": {},
            "posts": [],
            "menu_structure": None,
            "stats": {
                "pages_generated": 0,
                "posts_generated": 0,
                "total_time": 0
            }
        }

        start_time = time.time()
        page_count = 0
        total_pages = 4 + len(services)  # Home, About, Services, Contact + service pages

        # Generate Home page
        if on_progress:
            on_progress("Generating Home page", page_count + 1, total_pages)

        home = self.page_generator.generate_page(ContentRequest(
            page_type=PageType.HOME,
            title="Home",
            business_name=business_name,
            business_description=business_description,
            industry=industry,
            tone=tone,
            key_points=services[:3],
            call_to_action="Get Started Today"
        ))
        results["pages"]["home"] = home
        page_count += 1

        # Generate About page
        if on_progress:
            on_progress("Generating About page", page_count + 1, total_pages)

        about = self.page_generator.generate_page(ContentRequest(
            page_type=PageType.ABOUT,
            title="About Us",
            business_name=business_name,
            business_description=business_description,
            industry=industry,
            tone=tone
        ))
        results["pages"]["about"] = about
        page_count += 1

        # Generate Services overview
        if on_progress:
            on_progress("Generating Services page", page_count + 1, total_pages)

        services_page = self.page_generator.generate_page(ContentRequest(
            page_type=PageType.SERVICES,
            title="Our Services",
            business_name=business_name,
            business_description=business_description,
            industry=industry,
            tone=tone,
            key_points=services
        ))
        results["pages"]["services"] = services_page
        page_count += 1

        # Generate individual service pages
        for service in services:
            if on_progress:
                on_progress(f"Generating {service} page", page_count + 1, total_pages)

            service_page = self.page_generator.generate_page(ContentRequest(
                page_type=PageType.SERVICE_DETAIL,
                title=service,
                business_name=business_name,
                business_description=business_description,
                industry=industry,
                tone=tone,
                call_to_action=f"Learn more about {service}"
            ))

            slug = service.lower().replace(" ", "-")
            results["pages"][f"service-{slug}"] = service_page
            page_count += 1
            time.sleep(1)

        # Generate Contact page
        if on_progress:
            on_progress("Generating Contact page", page_count + 1, total_pages)

        contact = self.page_generator.generate_page(ContentRequest(
            page_type=PageType.CONTACT,
            title="Contact Us",
            business_name=business_name,
            business_description=business_description,
            industry=industry,
            tone=tone
        ))
        results["pages"]["contact"] = contact

        results["stats"]["pages_generated"] = len(results["pages"])

        # Generate blog posts if requested
        if include_blog and blog_topics:
            if on_progress:
                on_progress("Generating blog posts", 0, len(blog_topics))

            for i, topic in enumerate(blog_topics):
                if on_progress:
                    on_progress(f"Generating post: {topic}", i + 1, len(blog_topics))

                try:
                    post = self.blog_generator.generate_post(BlogPostRequest(
                        topic=topic,
                        business_name=business_name,
                        industry=industry,
                        tone=tone
                    ))
                    results["posts"].append(post)
                except Exception as e:
                    print(f"Failed to generate post '{topic}': {e}")

                time.sleep(1)

            results["stats"]["posts_generated"] = len(results["posts"])

        # Generate menu structure
        results["menu_structure"] = self._generate_menu_structure(services)

        results["stats"]["total_time"] = time.time() - start_time

        return results

    def _generate_menu_structure(self, services: list[str]) -> dict:
        """Generate suggested menu structure."""

        service_items = [
            {
                "title": service,
                "type": "page",
                "slug": f"service-{service.lower().replace(' ', '-')}"
            }
            for service in services
        ]

        return {
            "primary": {
                "location": "primary-menu",
                "items": [
                    {"title": "Home", "type": "page", "slug": "home"},
                    {"title": "About", "type": "page", "slug": "about"},
                    {
                        "title": "Services",
                        "type": "page",
                        "slug": "services",
                        "children": service_items
                    },
                    {"title": "Contact", "type": "page", "slug": "contact"}
                ]
            }
        }
```

**Time:** 4 hours total

---

### Step 9-10: CLI Extensions for AI Commands

**Why:** Expose AI capabilities through CLI for easy access and agent integration.

**Code:**

```python
# cli/ai.py

import click
import os
from pathlib import Path
import json
import yaml

def load_env():
    """Load environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v

def load_site_credentials(site_id: str) -> dict:
    """Load site credentials."""
    secrets_file = Path(f"secrets/projects/{site_id}.env")
    creds = {}
    if secrets_file.exists():
        with open(secrets_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    creds[k] = v
    return creds

@click.group()
def ai():
    """AI content generation commands."""
    load_env()

# ─────────────────────────────────────────────────────────────
# Page Generation
# ─────────────────────────────────────────────────────────────

@ai.command('generate-page')
@click.argument('site_id')
@click.option('--type', 'page_type', required=True,
              type=click.Choice(['home', 'about', 'services', 'service_detail',
                                'contact', 'faq', 'landing', 'custom']))
@click.option('--title', required=True)
@click.option('--business', required=True, help='Business name')
@click.option('--description', required=True, help='Business description')
@click.option('--industry', help='Industry context')
@click.option('--tone', default='professional',
              type=click.Choice(['professional', 'friendly', 'technical', 'casual']))
@click.option('--publish/--draft', default=False, help='Publish immediately or save as draft')
@click.option('--output', type=click.Path(), help='Save HTML to file instead of WordPress')
def generate_page(site_id, page_type, title, business, description, industry, tone, publish, output):
    """Generate a page using AI and optionally publish to WordPress."""

    from compiler.ai.content_generator import ContentGenerator, ContentRequest, PageType, Tone

    click.echo(f"Generating {page_type} page: {title}")

    generator = ContentGenerator()

    request = ContentRequest(
        page_type=PageType(page_type),
        title=title,
        business_name=business,
        business_description=description,
        industry=industry,
        tone=Tone(tone)
    )

    content = generator.generate_page(request)

    click.echo(f"✓ Generated {len(content.html_content.split())} words")
    click.echo(f"  Meta title: {content.meta_title}")
    click.echo(f"  Meta description: {content.meta_description[:60]}...")

    if output:
        # Save to file
        Path(output).write_text(content.html_content)
        click.echo(f"✓ Saved to {output}")
    else:
        # Publish to WordPress
        creds = load_site_credentials(site_id)

        if not creds.get('WP_APP_PASSWORD'):
            click.echo("✗ No WordPress credentials found. Use --output to save to file.")
            raise click.Abort()

        from compiler.wordpress.content import ContentManager, PageConfig

        cm = ContentManager(
            site_id,
            creds['WP_SITE_URL'],
            creds['WP_ADMIN_USER'],
            creds['WP_APP_PASSWORD']
        )

        page = cm.create_page(PageConfig(
            title=title,
            slug=content.suggested_slug,
            content=content.html_content,
            status='publish' if publish else 'draft'
        ))

        click.echo(f"✓ Created page: {page.url}")
        click.echo(f"  Status: {'published' if publish else 'draft'}")

# ─────────────────────────────────────────────────────────────
# Post Generation
# ─────────────────────────────────────────────────────────────

@ai.command('generate-post')
@click.argument('site_id')
@click.option('--topic', required=True)
@click.option('--business', required=True)
@click.option('--industry')
@click.option('--tone', default='professional')
@click.option('--words', default=1000, type=int)
@click.option('--publish/--draft', default=False)
@click.option('--output', type=click.Path())
def generate_post(site_id, topic, business, industry, tone, words, publish, output):
    """Generate a blog post using AI."""

    from compiler.ai.blog_generator import BlogGenerator, BlogPostRequest
    from compiler.ai.content_generator import Tone

    click.echo(f"Generating blog post: {topic}")

    generator = BlogGenerator()

    request = BlogPostRequest(
        topic=topic,
        business_name=business,
        industry=industry,
        tone=Tone(tone),
        word_count=words
    )

    post = generator.generate_post(request)

    click.echo(f"✓ Generated: {post.title}")
    click.echo(f"  Words: {len(post.html_content.split())}")
    click.echo(f"  Categories: {', '.join(post.suggested_categories)}")
    click.echo(f"  Tags: {', '.join(post.suggested_tags)}")

    if output:
        Path(output).write_text(post.html_content)
        click.echo(f"✓ Saved to {output}")
    else:
        creds = load_site_credentials(site_id)

        if not creds.get('WP_APP_PASSWORD'):
            click.echo("✗ No WordPress credentials. Use --output to save to file.")
            raise click.Abort()

        from compiler.wordpress.content import ContentManager, PostConfig

        cm = ContentManager(
            site_id,
            creds['WP_SITE_URL'],
            creds['WP_ADMIN_USER'],
            creds['WP_APP_PASSWORD']
        )

        wp_post = cm.create_post(PostConfig(
            title=post.title,
            slug=post.suggested_slug,
            content=post.html_content,
            status='publish' if publish else 'draft',
            categories=post.suggested_categories,
            tags=post.suggested_tags,
            excerpt=post.excerpt
        ))

        click.echo(f"✓ Created post: {wp_post.url}")

# ─────────────────────────────────────────────────────────────
# Content Revision
# ─────────────────────────────────────────────────────────────

@ai.command('revise-page')
@click.argument('site_id')
@click.argument('page_slug')
@click.option('--instructions', required=True, help='Revision instructions')
@click.option('--type', 'revision_type', default='improve',
              type=click.Choice(['rewrite', 'improve', 'expand', 'shorten',
                                'tone_change', 'add_section', 'fix_issues']))
@click.option('--publish/--draft', default=True)
def revise_page(site_id, page_slug, instructions, revision_type, publish):
    """Revise an existing page using AI."""

    from compiler.ai.content_reviser import ContentReviser, RevisionRequest, RevisionType

    creds = load_site_credentials(site_id)

    if not creds.get('WP_APP_PASSWORD'):
        click.echo("✗ No WordPress credentials found")
        raise click.Abort()

    from compiler.wordpress.rest_api import WordPressRESTClient

    client = WordPressRESTClient(
        creds['WP_SITE_URL'],
        creds['WP_ADMIN_USER'],
        creds['WP_APP_PASSWORD']
    )

    # Fetch current content
    click.echo(f"Fetching page: {page_slug}")
    page = client.get_page_by_slug(page_slug)

    if not page:
        click.echo(f"✗ Page not found: {page_slug}")
        raise click.Abort()

    # Get full content
    pages = client._get('pages', {'slug': page_slug})
    current_content = pages[0]['content']['rendered']

    click.echo(f"Revising page: {page.title}")
    click.echo(f"  Type: {revision_type}")
    click.echo(f"  Instructions: {instructions}")

    reviser = ContentReviser()

    result = reviser.revise(RevisionRequest(
        current_content=current_content,
        revision_type=RevisionType(revision_type),
        instructions=instructions
    ))

    click.echo(f"\n✓ Revision complete")
    click.echo(f"  Original: {result.original_length} words")
    click.echo(f"  Revised: {result.revised_length} words")
    click.echo(f"\nChanges:")
    click.echo(result.changes_summary)

    # Update page
    if click.confirm("\nApply changes to WordPress?"):
        from compiler.wordpress.content import ContentManager, PageConfig

        cm = ContentManager(
            site_id,
            creds['WP_SITE_URL'],
            creds['WP_ADMIN_USER'],
            creds['WP_APP_PASSWORD']
        )

        updated = client.update_page(
            page.id,
            content=result.revised_content,
            status='publish' if publish else 'draft'
        )

        click.echo(f"\n✓ Updated: {updated.url}")

# ─────────────────────────────────────────────────────────────
# Bulk Generation
# ─────────────────────────────────────────────────────────────

@ai.command('generate-services')
@click.argument('site_id')
@click.option('--services', required=True, help='Comma-separated service names')
@click.option('--business', required=True)
@click.option('--description', required=True)
@click.option('--industry')
@click.option('--publish/--draft', default=False)
def generate_services(site_id, services, business, description, industry, publish):
    """Generate pages for multiple services."""

    from compiler.ai.bulk_generator import BulkGenerator

    service_list = [s.strip() for s in services.split(',')]

    click.echo(f"Generating {len(service_list)} service pages")

    generator = BulkGenerator()

    def progress(current, total, name):
        click.echo(f"  [{current}/{total}] {name}")

    result = generator.generate_service_pages(
        services=service_list,
        business_name=business,
        business_description=description,
        industry=industry,
        on_progress=progress
    )

    click.echo(f"\n✓ Generated {result.successful}/{result.total} pages")

    if result.errors:
        click.echo("Errors:")
        for error in result.errors:
            click.echo(f"  ✗ {error}")

    # Publish to WordPress
    if result.successful > 0:
        creds = load_site_credentials(site_id)

        if creds.get('WP_APP_PASSWORD') and click.confirm("\nPublish to WordPress?"):
            from compiler.wordpress.content import ContentManager, PageConfig

            cm = ContentManager(
                site_id,
                creds['WP_SITE_URL'],
                creds['WP_ADMIN_USER'],
                creds['WP_APP_PASSWORD']
            )

            for r in result.results:
                if r["status"] == "success":
                    content = r["content"]
                    page = cm.create_page(PageConfig(
                        title=content.title,
                        slug=content.suggested_slug,
                        content=content.html_content,
                        status='publish' if publish else 'draft'
                    ))
                    click.echo(f"  ✓ {page.title}: {page.url}")

@ai.command('generate-website')
@click.argument('site_id')
@click.option('--business', required=True)
@click.option('--description', required=True)
@click.option('--industry', required=True)
@click.option('--services', required=True, help='Comma-separated services')
@click.option('--include-blog', is_flag=True)
@click.option('--blog-topics', help='Comma-separated blog topics')
@click.option('--publish/--draft', default=False)
def generate_website(site_id, business, description, industry, services, include_blog, blog_topics, publish):
    """Generate complete website content package."""

    from compiler.ai.bulk_generator import BulkGenerator

    service_list = [s.strip() for s in services.split(',')]
    topic_list = [t.strip() for t in blog_topics.split(',')] if blog_topics else []

    click.echo(f"Generating complete website for {business}")
    click.echo(f"  Services: {len(service_list)}")
    click.echo(f"  Blog posts: {len(topic_list) if include_blog else 0}")

    generator = BulkGenerator()

    def progress(stage, current, total):
        click.echo(f"  {stage} [{current}/{total}]")

    result = generator.generate_website_content(
        business_name=business,
        business_description=description,
        industry=industry,
        services=service_list,
        include_blog=include_blog,
        blog_topics=topic_list,
        on_progress=progress
    )

    click.echo(f"\n✓ Generation complete")
    click.echo(f"  Pages: {result['stats']['pages_generated']}")
    click.echo(f"  Posts: {result['stats']['posts_generated']}")
    click.echo(f"  Time: {result['stats']['total_time']:.1f}s")

    # Show menu structure
    click.echo("\nSuggested menu structure:")
    click.echo(yaml.dump(result['menu_structure'], default_flow_style=False))

    # Publish to WordPress
    creds = load_site_credentials(site_id)

    if creds.get('WP_APP_PASSWORD') and click.confirm("\nPublish all content to WordPress?"):
        from compiler.wordpress.content import ContentManager, PageConfig, PostConfig, MenuConfig

        cm = ContentManager(
            site_id,
            creds['WP_SITE_URL'],
            creds['WP_ADMIN_USER'],
            creds['WP_APP_PASSWORD']
        )

        # Create pages
        click.echo("\nCreating pages...")
        for slug, content in result['pages'].items():
            page = cm.create_page(PageConfig(
                title=content.title,
                slug=content.suggested_slug,
                content=content.html_content,
                status='publish' if publish else 'draft'
            ))
            click.echo(f"  ✓ {page.title}")

        # Create posts
        if result['posts']:
            click.echo("\nCreating posts...")
            for post_content in result['posts']:
                post = cm.create_post(PostConfig(
                    title=post_content.title,
                    slug=post_content.suggested_slug,
                    content=post_content.html_content,
                    status='publish' if publish else 'draft',
                    categories=post_content.suggested_categories,
                    tags=post_content.suggested_tags
                ))
                click.echo(f"  ✓ {post.title}")

        # Create menu
        click.echo("\nCreating menu...")
        menu_config = result['menu_structure']['primary']
        menu_id = cm.create_menu(MenuConfig(
            name="Primary Menu",
            location=menu_config['location'],
            items=menu_config['items']
        ))
        click.echo(f"  ✓ Menu created (ID: {menu_id})")

        click.echo(f"\n✓ Website content published!")
        click.echo(f"  URL: {creds['WP_SITE_URL']}")

if __name__ == '__main__':
    ai()
```

**Update main CLI:**

```python
# cli/main.py - add ai commands

from cli.ai import ai

# ... existing code ...

cli.add_command(ai)
```

**Time:** 4 hours total

---

### Step 11-12: Windsurf Agent Integration

**Why:** The whole point is for AI agents to use this system. We need proper context rules and documentation for Windsurf.

**Create agent context file:**

```markdown
# windsurf/agent_context.md

# Fabrik Site Manager - Agent Context

You are a Site Reliability Engineer and Content Manager with full control over WordPress sites deployed via Fabrik.

## Your Capabilities

### Infrastructure Management
- Deploy new WordPress sites: `fabrik apply <id>`
- Check site status: `fabrik status <id>`
- View logs: `fabrik logs <id>`
- Destroy sites: `fabrik destroy <id>`

### WordPress Operations
- Install themes: `fabrik wp theme install <site> <theme>`
- Install plugins: `fabrik wp plugin install <site> <plugin>`
- Run WP-CLI: `fabrik wp cli <site> "<command>"`

### Content Management
- Create pages: `fabrik wp page create <site> --title="..." --slug="..."`
- Create posts: `fabrik wp post create <site> --title="..." --slug="..."`
- Create menus: `fabrik wp menu create <site> <name> --location=...`

### AI Content Generation
- Generate pages: `fabrik ai generate-page <site> --type=... --title="..." --business="..." --description="..."`
- Generate posts: `fabrik ai generate-post <site> --topic="..." --business="..."`
- Revise content: `fabrik ai revise-page <site> <slug> --instructions="..."`
- Generate services: `fabrik ai generate-services <site> --services="..." --business="..." --description="..."`
- Generate website: `fabrik ai generate-website <site> --business="..." --description="..." --industry="..." --services="..."`

## Available Page Types
- home, about, services, service_detail, contact, faq, landing, custom

## Available Tones
- professional, friendly, technical, casual, formal, persuasive

## Workflow Examples

### Create a New Client Website

1. Create spec:
   ```bash
   fabrik new wp-site client-xyz --domain=clientxyz.com
   ```

2. Edit spec if needed:
   ```bash
   # Edit specs/client-xyz/spec.yaml
   ```

3. Deploy:
   ```bash
   fabrik apply client-xyz
   ```

4. Generate content:
   ```bash
   fabrik ai generate-website client-xyz \
     --business="XYZ Corporation" \
     --description="B2B manufacturing company specializing in precision parts" \
     --industry="Manufacturing" \
     --services="CNC Machining,Quality Control,Design Services" \
     --publish
   ```

5. Report to user:
   - Site URL
   - Admin URL
   - What was created

### Add New Content to Existing Site

1. Generate page:
   ```bash
   fabrik ai generate-page existing-site \
     --type=service_detail \
     --title="New Service" \
     --business="Company Name" \
     --description="What they do" \
     --publish
   ```

2. Add to menu if needed:
   ```bash
   fabrik wp cli existing-site "menu item add-post primary <page_id>"
   ```

### Revise Content Based on Feedback

1. Fetch and revise:
   ```bash
   fabrik ai revise-page site-id about \
     --instructions="Make more professional, add company history section, emphasize quality"
   ```

2. Confirm changes applied

## Important Rules

1. Always confirm destructive operations with user
2. Use --draft first for review, then publish
3. Report what was created with URLs
4. If content generation fails, offer to try again or adjust parameters
5. When creating websites, generate menu structure automatically
6. Always set SEO metadata (title, description)

## Error Handling

- If WordPress credentials missing: suggest running `fabrik apply` first
- If page not found: check slug spelling, list existing pages
- If generation fails: check API keys, retry with different parameters
- If deployment fails: check logs with `fabrik logs <id>`

## Response Format

When completing tasks:
1. State what you're doing
2. Run the commands
3. Report results with URLs
4. Ask if further changes needed

Example:
"I'll create a new About page for your site.

Running: fabrik ai generate-page mysite --type=about --title="About Us" --business="ACME Corp" --description="Manufacturing company" --publish

✓ Created page: https://mysite.com/about-us

The page includes:
- Company overview
- Mission and values
- Team section
- History

Would you like me to revise anything or add more pages?"
```

**Create agent rules file:**

```yaml
# windsurf/rules.yaml

name: fabrik-site-manager
version: "1.0"

description: |
  Manage WordPress sites and content through Fabrik CLI.
  Can deploy infrastructure, configure WordPress, and generate AI content.

capabilities:
  - deploy_sites
  - configure_wordpress
  - generate_content
  - revise_content
  - manage_menus

tools:
  - name: fabrik
    description: Main CLI for site deployment and management
    commands:
      - new
      - plan
      - apply
      - status
      - logs
      - destroy
      - wp
      - ai

  - name: fabrik wp
    description: WordPress management commands
    subcommands:
      - theme list/install/activate
      - plugin list/install/activate/deactivate
      - page list/create
      - post list/create
      - menu create
      - cli

  - name: fabrik ai
    description: AI content generation commands
    subcommands:
      - generate-page
      - generate-post
      - revise-page
      - generate-services
      - generate-website

behaviors:
  - name: confirm_destructive
    description: Always confirm before destroying sites or overwriting content

  - name: draft_first
    description: Generate content as draft first, then publish after approval

  - name: report_urls
    description: Always report created URLs to user

  - name: suggest_next_steps
    description: After completing a task, suggest relevant next steps

examples:
  - trigger: "Create a website for [company]"
    actions:
      - "fabrik new wp-site <id> --domain=<domain>"
      - "fabrik apply <id>"
      - "fabrik ai generate-website <id> --business=<company> ..."

  - trigger: "Add a blog post about [topic]"
    actions:
      - "fabrik ai generate-post <site> --topic=<topic> --business=<business>"

  - trigger: "Make the [page] more [adjective]"
    actions:
      - "fabrik ai revise-page <site> <slug> --instructions='Make more <adjective>'"
```

**Time:** 4 hours total

---

### Phase 3 Complete

After completing all steps, you have:

```
✓ LLM client wrapper (Claude + OpenAI with fallback)
✓ Page generation from prompts (all page types)
✓ Blog post generation with SEO metadata
✓ SEO optimization tools
✓ Content revision system
✓ Bulk generation (services, FAQ, blog series)
✓ Complete website generation
✓ CLI commands for all AI operations
✓ Windsurf agent integration with context and rules
```

**New CLI commands:**

```bash
# Page generation
fabrik ai generate-page <site> --type=about --title="About Us" --business="..." --description="..."

# Post generation
fabrik ai generate-post <site> --topic="..." --business="..."

# Content revision
fabrik ai revise-page <site> <slug> --instructions="..."

# Bulk generation
fabrik ai generate-services <site> --services="A,B,C" --business="..." --description="..."

# Complete website
fabrik ai generate-website <site> --business="..." --description="..." --industry="..." --services="..."
```

---

### What Windsurf Agents Can Now Do

```
User: "Create a professional website for TechStart Inc, a SaaS startup
       offering project management software. Include Home, About,
       Features, Pricing, and Contact pages."

Agent:
[Creates spec] fabrik new wp-site techstart --domain=techstart.io
[Deploys] fabrik apply techstart
[Generates content] fabrik ai generate-website techstart \
  --business="TechStart Inc" \
  --description="SaaS startup offering intuitive project management software for teams" \
  --industry="Software/SaaS" \
  --services="Project Tracking,Team Collaboration,Resource Management,Reporting" \
  --publish

"I've created the TechStart website. Here's what's live:

- Home: https://techstart.io
- About: https://techstart.io/about
- Features: https://techstart.io/services (4 feature pages)
- Contact: https://techstart.io/contact

The site includes:
- Professional design-ready content
- SEO metadata on all pages
- Primary navigation menu
- Calls to action throughout

Would you like me to:
- Add a pricing page?
- Create some blog posts?
- Revise any of the content?"
```

---

### Phase 3 Summary

| Step | Task | Time |
|------|------|------|
| 1 | LLM Client Wrapper | 2 hrs |
| 2 | Page Generation | 2 hrs |
| 3 | Post Generation | 2 hrs |
| 4 | SEO Meta Generation | 1 hr |
| 5 | Content Revision System | 2 hrs |
| 6-8 | Bulk Generation Tools | 4 hrs |
| 9-10 | CLI Extensions | 4 hrs |
| 11-12 | Windsurf Agent Integration | 4 hrs |

**Total: ~24 hours (4-5 days)**

---

### What's Next (Phase 4+ Preview)

With Phase 3 complete, you have a full AI-powered site factory. The remaining phases add operational improvements:

- **Phase 4:** Cloudflare DNS migration for cleaner automation
- **Phase 5:** Staging environments for testing
- **Phase 6:** Advanced monitoring (Grafana, Prometheus)
- **Phase 7:** Multi-server scaling
- **Phase 8:** n8n for business workflow automation

But Phases 1-3 give you the core product: **deploy sites, automate WordPress, generate content with AI**.

---
