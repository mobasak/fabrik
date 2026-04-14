"""Contact forms creation stage."""

import logging
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.forms import FormCreator
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Create contact forms."""
    result = StageResult(name="forms", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )
        contact = spec.get("contact", {})
        form_config = contact.get("form", {})

        if not contact:
            result.skipped = True
            result.metadata["skipped_reason"] = "no contact section in spec"
        elif dry_run:
            result.metadata["dry_run"] = {
                "recipient": contact.get("email", ""),
                "fields": form_config.get("fields", ["name", "email", "message"]),
            }
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for forms stage")
            creator = FormCreator(site_name, wp)

            # Check if form plugin is available
            plugin = creator.detect_form_plugin()
            result.metadata["form_plugin"] = plugin
            if plugin:
                created = creator.create_contact_form(
                    title="Contact Form",
                    recipient=form_config.get("recipient") or contact.get("email", ""),
                    fields=form_config.get("fields", ["name", "email", "message"]),
                )
                result.metadata["form_id"] = created.id
                result.metadata["shortcode"] = created.shortcode
                logger.info("Contact form created via %s: %s", plugin, created.shortcode)
            else:
                result.warnings.append(
                    "No active form plugin detected (wpforms/cf7) — skipping form creation"
                )
                logger.warning("No active form plugin detected")
                result.skipped = True

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
