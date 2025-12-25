"""
WordPress Legal Content Generator - Generate legal pages.

Handles:
- Privacy Policy
- Terms of Service
- Cookie Policy
- GDPR compliance pages
"""

import os
from dataclasses import dataclass
from typing import Optional

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


@dataclass
class LegalPage:
    """Generated legal page content."""
    title: str
    slug: str
    html: str
    last_updated: str = ""


class LegalContentGenerator:
    """
    Generate legal pages for WordPress sites.
    
    Uses AI to generate customized legal content based on:
    - Company information
    - Services offered
    - Data collection practices
    - Jurisdiction
    
    Usage:
        generator = LegalContentGenerator()
        privacy = generator.generate_privacy_policy(brand, contact)
        terms = generator.generate_terms_of_service(brand)
    """
    
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize legal content generator.
        
        Args:
            api_key: Anthropic API key
            model: Model to use
        """
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package required: pip install anthropic")
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.model = model or self.DEFAULT_MODEL
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def generate_privacy_policy(
        self,
        brand: dict,
        contact: dict,
        data_practices: Optional[dict] = None,
        language: str = "en",
    ) -> LegalPage:
        """
        Generate a Privacy Policy page.
        
        Args:
            brand: Brand information (name, etc.)
            contact: Contact information (email, address)
            data_practices: Optional data collection details
            language: Output language
            
        Returns:
            LegalPage with HTML content
        """
        company_name = brand.get("name", "Company")
        contact_email = contact.get("email", "privacy@example.com")
        website = brand.get("website", contact.get("website", ""))
        
        prompt = f"""Generate a comprehensive Privacy Policy for {company_name}.

## Company Information
- Company Name: {company_name}
- Contact Email: {contact_email}
- Website: {website}

## Data Practices (typical for a business website)
- Contact form submissions (name, email, message)
- Analytics cookies (Google Analytics)
- Essential cookies for site functionality
- Email newsletter subscription (if applicable)

## Requirements
1. GDPR compliant
2. CCPA compliant
3. Clear, readable language
4. Proper HTML formatting with H2, H3 headings
5. Include last updated date placeholder
6. Cover: data collection, usage, storage, sharing, rights, cookies, contact

{"Generate in Turkish." if language == "tr" else ""}

Output clean HTML only, no markdown or code blocks."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return LegalPage(
            title="Privacy Policy",
            slug="privacy-policy",
            html=response.content[0].text,
        )
    
    def generate_terms_of_service(
        self,
        brand: dict,
        contact: dict,
        services: Optional[list] = None,
        language: str = "en",
    ) -> LegalPage:
        """
        Generate Terms of Service page.
        
        Args:
            brand: Brand information
            contact: Contact information
            services: Optional list of services offered
            language: Output language
            
        Returns:
            LegalPage with HTML content
        """
        company_name = brand.get("name", "Company")
        contact_email = contact.get("email", "legal@example.com")
        
        services_desc = ""
        if services:
            services_desc = f"Services offered: {', '.join(services)}"
        
        prompt = f"""Generate Terms of Service for {company_name}.

## Company Information
- Company Name: {company_name}
- Contact Email: {contact_email}
{services_desc}

## Requirements
1. Professional business website terms
2. Clear, readable language
3. Proper HTML formatting with H2, H3 headings
4. Cover: acceptance, use license, disclaimers, limitations, governing law, changes
5. Include last updated date placeholder

{"Generate in Turkish." if language == "tr" else ""}

Output clean HTML only, no markdown or code blocks."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return LegalPage(
            title="Terms of Service",
            slug="terms-of-service",
            html=response.content[0].text,
        )
    
    def generate_cookie_policy(
        self,
        brand: dict,
        contact: dict,
        language: str = "en",
    ) -> LegalPage:
        """
        Generate Cookie Policy page.
        
        Args:
            brand: Brand information
            contact: Contact information
            language: Output language
            
        Returns:
            LegalPage with HTML content
        """
        company_name = brand.get("name", "Company")
        
        prompt = f"""Generate a Cookie Policy for {company_name}.

## Cookies Used (typical)
1. Essential cookies (session, security)
2. Analytics cookies (Google Analytics)
3. Performance cookies (caching, CDN)

## Requirements
1. GDPR compliant
2. Clear explanation of each cookie type
3. How to manage/disable cookies
4. Proper HTML formatting
5. Include last updated date

{"Generate in Turkish." if language == "tr" else ""}

Output clean HTML only."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return LegalPage(
            title="Cookie Policy",
            slug="cookie-policy",
            html=response.content[0].text,
        )
    
    def generate_all(
        self,
        brand: dict,
        contact: dict,
        language: str = "en",
    ) -> dict[str, LegalPage]:
        """
        Generate all standard legal pages.
        
        Args:
            brand: Brand information
            contact: Contact information
            language: Output language
            
        Returns:
            Dict mapping slug to LegalPage
        """
        pages = {}
        
        pages["privacy-policy"] = self.generate_privacy_policy(brand, contact, language=language)
        pages["terms-of-service"] = self.generate_terms_of_service(brand, contact, language=language)
        pages["cookie-policy"] = self.generate_cookie_policy(brand, contact, language=language)
        
        return pages


# Fallback templates for when AI is not available
PRIVACY_POLICY_TEMPLATE = """
<h2>Privacy Policy</h2>
<p><em>Last updated: {date}</em></p>

<h3>1. Information We Collect</h3>
<p>{company_name} ("we", "our", "us") collects information you provide directly to us, such as when you fill out a contact form, subscribe to our newsletter, or communicate with us.</p>

<h3>2. How We Use Your Information</h3>
<p>We use the information we collect to:</p>
<ul>
<li>Respond to your inquiries and requests</li>
<li>Send you updates and marketing communications (with your consent)</li>
<li>Improve our website and services</li>
<li>Comply with legal obligations</li>
</ul>

<h3>3. Cookies</h3>
<p>We use cookies and similar technologies to enhance your experience on our website. You can control cookies through your browser settings.</p>

<h3>4. Your Rights</h3>
<p>You have the right to access, correct, or delete your personal data. Contact us at {contact_email} to exercise these rights.</p>

<h3>5. Contact Us</h3>
<p>For questions about this Privacy Policy, contact us at {contact_email}.</p>
"""

TERMS_OF_SERVICE_TEMPLATE = """
<h2>Terms of Service</h2>
<p><em>Last updated: {date}</em></p>

<h3>1. Acceptance of Terms</h3>
<p>By accessing and using the {company_name} website, you accept and agree to be bound by these Terms of Service.</p>

<h3>2. Use License</h3>
<p>Permission is granted to temporarily access the materials on our website for personal, non-commercial use only.</p>

<h3>3. Disclaimer</h3>
<p>The materials on our website are provided on an 'as is' basis. We make no warranties, expressed or implied.</p>

<h3>4. Limitations</h3>
<p>In no event shall {company_name} be liable for any damages arising out of the use or inability to use our website.</p>

<h3>5. Changes to Terms</h3>
<p>We may revise these terms at any time. By using this website, you agree to be bound by the current version.</p>

<h3>6. Contact</h3>
<p>Questions about these Terms should be sent to {contact_email}.</p>
"""


def generate_legal_pages(
    brand: dict,
    contact: dict,
    language: str = "en",
    use_ai: bool = True,
    api_key: Optional[str] = None,
) -> dict[str, LegalPage]:
    """
    Convenience function to generate all legal pages.
    
    Args:
        brand: Brand information
        contact: Contact information
        language: Output language
        use_ai: Whether to use AI generation
        api_key: Optional API key
        
    Returns:
        Dict mapping slug to LegalPage
    """
    if use_ai and HAS_ANTHROPIC:
        try:
            generator = LegalContentGenerator(api_key=api_key)
            return generator.generate_all(brand, contact, language)
        except Exception:
            pass
    
    # Fallback to templates
    from datetime import date
    today = date.today().isoformat()
    company_name = brand.get("name", "Company")
    contact_email = contact.get("email", "contact@example.com")
    
    return {
        "privacy-policy": LegalPage(
            title="Privacy Policy",
            slug="privacy-policy",
            html=PRIVACY_POLICY_TEMPLATE.format(
                date=today,
                company_name=company_name,
                contact_email=contact_email,
            ),
        ),
        "terms-of-service": LegalPage(
            title="Terms of Service",
            slug="terms-of-service",
            html=TERMS_OF_SERVICE_TEMPLATE.format(
                date=today,
                company_name=company_name,
                contact_email=contact_email,
            ),
        ),
    }
