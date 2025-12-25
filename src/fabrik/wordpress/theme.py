"""
WordPress Theme Customizer - Apply brand styles to GeneratePress theme.

Handles:
- Global colors (primary, secondary, accent)
- Typography (heading/body fonts)
- Layout settings (container width, sidebar)
- Custom CSS injection
"""

import json
from dataclasses import dataclass
from typing import Optional

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client


@dataclass
class BrandColors:
    """Brand color palette."""
    primary: str = "#1e3a5f"
    secondary: str = "#0891b2"
    accent: str = "#ea580c"
    background: str = "#ffffff"
    text: str = "#1a1a1a"
    text_light: str = "#6b7280"


@dataclass
class BrandFonts:
    """Brand typography."""
    heading: str = "Inter"
    body: str = "Inter"
    source: str = "google"  # google, adobe, system


class ThemeCustomizer:
    """
    Apply brand customizations to GeneratePress theme.
    
    GeneratePress stores settings in:
    - generate_settings (option) - main theme settings
    - theme_mods_flavor-starter (option) - theme mods for child theme
    
    Usage:
        customizer = ThemeCustomizer("wp-test")
        customizer.apply_colors(colors)
        customizer.apply_fonts(fonts)
        customizer.apply_layout(width=1200)
    """
    
    # GeneratePress global color slugs
    GP_COLOR_SLUGS = {
        "primary": "contrast",
        "secondary": "contrast-2", 
        "accent": "accent",
        "background": "base",
        "text": "contrast-3",
    }
    
    def __init__(self, site_name: str, wp_client: Optional[WordPressClient] = None):
        """
        Initialize theme customizer.
        
        Args:
            site_name: WordPress site name (container prefix)
            wp_client: Optional WP-CLI client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)
    
    def apply_colors(self, colors: BrandColors | dict) -> dict:
        """
        Apply brand colors to GeneratePress global colors.
        
        Args:
            colors: BrandColors instance or dict with color values
            
        Returns:
            Dict of applied colors
        """
        if isinstance(colors, dict):
            colors = BrandColors(**{k: v for k, v in colors.items() if hasattr(BrandColors, k)})
        
        applied = {}
        
        # Build global colors array for GP
        global_colors = []
        
        if colors.primary:
            global_colors.append({
                "slug": "contrast",
                "color": colors.primary,
                "name": "Primary"
            })
            applied["primary"] = colors.primary
        
        if colors.secondary:
            global_colors.append({
                "slug": "contrast-2",
                "color": colors.secondary,
                "name": "Secondary"
            })
            applied["secondary"] = colors.secondary
        
        if colors.accent:
            global_colors.append({
                "slug": "accent",
                "color": colors.accent,
                "name": "Accent"
            })
            applied["accent"] = colors.accent
        
        if colors.background:
            global_colors.append({
                "slug": "base",
                "color": colors.background,
                "name": "Background"
            })
            applied["background"] = colors.background
        
        if colors.text:
            global_colors.append({
                "slug": "contrast-3",
                "color": colors.text,
                "name": "Text"
            })
            applied["text"] = colors.text
        
        # Apply via theme mod
        colors_json = json.dumps(global_colors)
        self.wp.run(f"theme mod set global_colors '{colors_json}'")
        
        return applied
    
    def apply_fonts(self, fonts: BrandFonts | dict) -> dict:
        """
        Apply brand fonts to GeneratePress typography.
        
        Args:
            fonts: BrandFonts instance or dict with font settings
            
        Returns:
            Dict of applied fonts
        """
        if isinstance(fonts, dict):
            fonts = BrandFonts(**{k: v for k, v in fonts.items() if hasattr(BrandFonts, k)})
        
        applied = {}
        
        # Body font
        if fonts.body:
            self.wp.run(f"theme mod set font_body '{fonts.body}'")
            applied["body"] = fonts.body
        
        # Heading fonts (GP has separate settings for each heading level)
        if fonts.heading:
            # Set for all headings
            for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                self.wp.run(f"theme mod set font_{level} '{fonts.heading}'")
            applied["heading"] = fonts.heading
        
        return applied
    
    def apply_layout(
        self,
        container_width: int = 1200,
        sidebar: str = "no-sidebar",
        header_layout: str = "default"
    ) -> dict:
        """
        Apply layout settings to GeneratePress.
        
        Args:
            container_width: Container width in pixels
            sidebar: Sidebar layout (no-sidebar, right-sidebar, left-sidebar)
            header_layout: Header layout
            
        Returns:
            Dict of applied settings
        """
        applied = {}
        
        # Container width
        self.wp.run(f"theme mod set container_width '{container_width}'")
        applied["container_width"] = container_width
        
        # Sidebar layout
        self.wp.run(f"theme mod set layout_setting '{sidebar}'")
        applied["sidebar"] = sidebar
        
        return applied
    
    def apply_custom_css(self, css: str) -> bool:
        """
        Add custom CSS to the theme.
        
        Args:
            css: CSS string to add
            
        Returns:
            True if successful
        """
        if not css.strip():
            return False
        
        # Escape single quotes for shell
        escaped_css = css.replace("'", "'\\''")
        
        # Add via customizer additional CSS
        self.wp.run(f"theme mod set custom_css '{escaped_css}'")
        
        return True
    
    def apply_from_spec(self, spec: dict) -> dict:
        """
        Apply all theme customizations from site spec.
        
        Args:
            spec: Site specification dict with 'brand' and 'theme' sections
            
        Returns:
            Dict of all applied customizations
        """
        results = {}
        
        brand = spec.get("brand", {})
        theme = spec.get("theme", {})
        
        # Colors
        if colors := brand.get("colors"):
            results["colors"] = self.apply_colors(colors)
        
        # Fonts
        if fonts := brand.get("fonts"):
            results["fonts"] = self.apply_fonts(fonts)
        
        # Layout from theme settings
        gp_settings = theme.get("generatepress", {})
        if gp_settings:
            results["layout"] = self.apply_layout(
                container_width=gp_settings.get("container_width", 1200),
                sidebar=gp_settings.get("sidebar", "no-sidebar"),
            )
        
        # Custom CSS
        if custom_css := theme.get("custom_css"):
            results["custom_css"] = self.apply_custom_css(custom_css)
        
        return results
    
    def install_theme(self, activate: bool = True) -> str:
        """
        Install GeneratePress theme from WordPress.org.
        
        Args:
            activate: Whether to activate after install
            
        Returns:
            Installation result message
        """
        return self.wp.theme_install("generatepress", activate=activate)
    
    def get_active_theme(self) -> str:
        """Get currently active theme."""
        return self.wp.run("theme list --status=active --field=name")


def apply_theme(site_name: str, spec: dict) -> dict:
    """
    Convenience function to apply theme customizations.
    
    Args:
        site_name: WordPress site name
        spec: Site specification dict
        
    Returns:
        Dict of applied customizations
    """
    customizer = ThemeCustomizer(site_name)
    return customizer.apply_from_spec(spec)
