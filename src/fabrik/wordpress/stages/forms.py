"""Contact forms creation stage."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.forms import FormCreator
from fabrik.wordpress.stages import StageResult, time_stage


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
            # No contact info: not an error
            pass
        elif dry_run:
            # Dry-run: just log intent
            pass
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for forms stage")
            creator = FormCreator(site_name, wp)

            # Check if form plugin is available
            plugin = creator.detect_form_plugin()
            if plugin:
                creator.create_contact_form(
                    title="Contact Form",
                    recipient=form_config.get("recipient") or contact.get("email", ""),
                    fields=form_config.get("fields", ["name", "email", "message"]),
                )
            else:
                # No plugin: not an error, just skip
                pass

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
