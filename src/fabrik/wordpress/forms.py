"""
WordPress Form Creator - Create contact forms via WPForms/CF7.

Handles:
- Contact form creation
- Email notification configuration
- Form field setup
"""

import json
from dataclasses import dataclass
from typing import Optional

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client


@dataclass
class CreatedForm:
    """Created form details."""
    id: int
    title: str
    shortcode: str
    fields: list[str]


class FormCreator:
    """
    Create WordPress contact forms.
    
    Supports:
    - WPForms (preferred)
    - Contact Form 7 (fallback)
    
    Usage:
        creator = FormCreator("wp-test")
        form = creator.create_contact_form(
            title="Contact Us",
            recipient="info@example.com",
            fields=["name", "email", "phone", "message"]
        )
    """
    
    # Default field configurations
    DEFAULT_FIELDS = {
        "name": {"label": "Name", "type": "text", "required": True},
        "email": {"label": "Email", "type": "email", "required": True},
        "phone": {"label": "Phone", "type": "tel", "required": False},
        "company": {"label": "Company", "type": "text", "required": False},
        "subject": {"label": "Subject", "type": "text", "required": False},
        "message": {"label": "Message", "type": "textarea", "required": True},
    }
    
    def __init__(self, site_name: str, wp_client: Optional[WordPressClient] = None):
        """
        Initialize form creator.
        
        Args:
            site_name: WordPress site name
            wp_client: Optional WP-CLI client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)
        self._form_plugin = None
    
    def detect_form_plugin(self) -> Optional[str]:
        """Detect installed form plugin."""
        if self._form_plugin:
            return self._form_plugin
        
        plugins = self.wp.plugin_list()
        
        for plugin in plugins:
            name = plugin.get("name", "")
            status = plugin.get("status", "")
            
            if status != "active":
                continue
            
            if "wpforms" in name.lower():
                self._form_plugin = "wpforms"
                return "wpforms"
            elif "contact-form-7" in name.lower():
                self._form_plugin = "cf7"
                return "cf7"
        
        return None
    
    def create_contact_form(
        self,
        title: str = "Contact Form",
        recipient: str = "",
        fields: Optional[list] = None,
        success_message: str = "Thanks for contacting us! We will be in touch with you shortly.",
    ) -> CreatedForm:
        """
        Create a contact form.
        
        Args:
            title: Form title
            recipient: Email recipient for submissions
            fields: List of field names or field configs
            success_message: Message shown after submission
            
        Returns:
            CreatedForm with details and shortcode
        """
        plugin = self.detect_form_plugin()
        
        if fields is None:
            fields = ["name", "email", "message"]
        
        if plugin == "wpforms":
            return self._create_wpforms(title, recipient, fields, success_message)
        elif plugin == "cf7":
            return self._create_cf7(title, recipient, fields, success_message)
        else:
            raise RuntimeError("No supported form plugin found (WPForms or CF7)")
    
    def _create_wpforms(
        self,
        title: str,
        recipient: str,
        fields: list,
        success_message: str,
    ) -> CreatedForm:
        """Create form using WPForms."""
        # Build form fields
        form_fields = {}
        for i, field in enumerate(fields):
            if isinstance(field, str):
                field_config = self.DEFAULT_FIELDS.get(field, {
                    "label": field.title(),
                    "type": "text",
                    "required": False
                })
            else:
                field_config = field
            
            form_fields[str(i)] = {
                "id": str(i),
                "type": self._map_field_type(field_config.get("type", "text"), "wpforms"),
                "label": field_config.get("label", "Field"),
                "required": "1" if field_config.get("required", False) else "0",
                "size": "large",
            }
        
        # Build form post content
        form_data = {
            "fields": form_fields,
            "settings": {
                "form_title": title,
                "submit_text": "Submit",
                "submit_text_processing": "Sending...",
                "notification_enable": "1",
                "notifications": {
                    "1": {
                        "email": recipient or "{admin_email}",
                        "subject": f"New submission from {title}",
                        "sender_name": "{field_id=\"0\"}",
                        "sender_address": "{field_id=\"1\"}",
                        "message": "{all_fields}",
                    }
                },
                "confirmations": {
                    "1": {
                        "type": "message",
                        "message": success_message,
                    }
                },
            },
        }
        
        # Create form as custom post type
        form_content = json.dumps(form_data)
        escaped_content = form_content.replace("'", "'\\''")
        
        output = self.wp.run(
            f"post create --post_type=wpforms --post_title='{title}' "
            f"--post_status=publish --post_content='{escaped_content}' --porcelain"
        )
        form_id = int(output.strip())
        
        return CreatedForm(
            id=form_id,
            title=title,
            shortcode=f"[wpforms id=\"{form_id}\"]",
            fields=[f.get("label", f) if isinstance(f, dict) else f for f in fields],
        )
    
    def _create_cf7(
        self,
        title: str,
        recipient: str,
        fields: list,
        success_message: str,
    ) -> CreatedForm:
        """Create form using Contact Form 7."""
        # Build form HTML
        form_html = []
        mail_body = []
        
        for field in fields:
            if isinstance(field, str):
                field_config = self.DEFAULT_FIELDS.get(field, {
                    "label": field.title(),
                    "type": "text",
                    "required": False
                })
                field_name = field
            else:
                field_config = field
                field_name = field.get("name", field.get("label", "field").lower())
            
            label = field_config.get("label", field_name.title())
            field_type = self._map_field_type(field_config.get("type", "text"), "cf7")
            required = field_config.get("required", False)
            
            req_marker = "*" if required else ""
            cf7_field = f"[{field_type}{req_marker} {field_name}]"
            
            if field_type == "textarea":
                form_html.append(f"<label>{label}{req_marker}\n    {cf7_field}</label>")
            else:
                form_html.append(f"<label>{label}{req_marker}\n    {cf7_field}</label>")
            
            mail_body.append(f"{label}: [{field_name}]")
        
        form_html.append("[submit \"Submit\"]")
        
        form_content = "\n\n".join(form_html)
        mail_content = "\n".join(mail_body)
        
        # Create CF7 form post
        output = self.wp.run(
            f"post create --post_type=wpcf7_contact_form --post_title='{title}' "
            f"--post_status=publish --porcelain"
        )
        form_id = int(output.strip())
        
        # Set form content and mail settings
        self.wp.run(f"post meta update {form_id} _form '{form_content}'")
        
        mail_settings = json.dumps({
            "subject": f"New submission: {title}",
            "sender": f"[your-name] <[your-email]>",
            "recipient": recipient or "[_site_admin_email]",
            "body": mail_content,
            "additional_headers": "",
            "attachments": "",
            "use_html": False,
        })
        self.wp.run(f"post meta update {form_id} _mail '{mail_settings}'")
        
        # Set confirmation message
        messages = json.dumps({
            "mail_sent_ok": success_message,
        })
        self.wp.run(f"post meta update {form_id} _messages '{messages}'")
        
        return CreatedForm(
            id=form_id,
            title=title,
            shortcode=f"[contact-form-7 id=\"{form_id}\" title=\"{title}\"]",
            fields=[f.get("label", f) if isinstance(f, dict) else f for f in fields],
        )
    
    def _map_field_type(self, field_type: str, plugin: str) -> str:
        """Map generic field type to plugin-specific type."""
        if plugin == "wpforms":
            type_map = {
                "text": "text",
                "email": "email",
                "tel": "phone",
                "textarea": "textarea",
                "select": "select",
                "checkbox": "checkbox",
                "radio": "radio",
            }
        else:  # cf7
            type_map = {
                "text": "text",
                "email": "email",
                "tel": "tel",
                "textarea": "textarea",
                "select": "select",
                "checkbox": "checkbox",
                "radio": "radio",
            }
        return type_map.get(field_type, "text")
    
    def list_forms(self) -> list[dict]:
        """List all forms."""
        plugin = self.detect_form_plugin()
        
        if plugin == "wpforms":
            post_type = "wpforms"
        elif plugin == "cf7":
            post_type = "wpcf7_contact_form"
        else:
            return []
        
        try:
            output = self.wp.run(f"post list --post_type={post_type} --format=json")
            return json.loads(output)
        except (RuntimeError, json.JSONDecodeError):
            return []
    
    def delete_form(self, form_id: int) -> bool:
        """Delete a form."""
        try:
            self.wp.run(f"post delete {form_id} --force")
            return True
        except RuntimeError:
            return False


def create_contact_form(
    site_name: str,
    contact: dict,
    form_title: str = "Contact Form",
) -> CreatedForm:
    """
    Convenience function to create a contact form from spec.
    
    Args:
        site_name: WordPress site name
        contact: Contact section from site spec
        form_title: Form title
        
    Returns:
        CreatedForm with shortcode
    """
    creator = FormCreator(site_name)
    
    recipient = contact.get("email", contact.get("form_recipient", ""))
    fields = contact.get("form_fields", ["name", "email", "message"])
    
    return creator.create_contact_form(
        title=form_title,
        recipient=recipient,
        fields=fields,
    )
