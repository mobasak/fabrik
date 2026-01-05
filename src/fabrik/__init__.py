"""
Fabrik - Deployment automation CLI for AI-powered infrastructure.

Enables spec-driven deployment of Python APIs, WordPress sites,
and AI-integrated applications via Coolify.
"""

__version__ = "0.1.0"
__author__ = "Özgür Başak"

from fabrik.spec_loader import Spec, create_spec, load_spec, save_spec
from fabrik.template_renderer import TemplateRenderer, list_templates, render_template

__all__ = [
    "load_spec",
    "save_spec",
    "create_spec",
    "Spec",
    "render_template",
    "list_templates",
    "TemplateRenderer",
]
