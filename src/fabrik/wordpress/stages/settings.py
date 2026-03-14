"""WordPress settings configuration stage."""

import json
import logging
import os
import secrets
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.settings import SettingsApplicator
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


def _derive_editor_username(email: str) -> str:
    """Derive editor username from email consistently with SettingsApplicator."""
    return email.split("@")[0].replace(".", "_").replace("+", "_")


def _write_credentials_report(build_dir: Path, payload: dict[str, str | bool]) -> Path:
    """Write credentials artifact with restrictive permissions."""
    reports_dir = build_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    credentials_path = reports_dir / "credentials.json"
    credentials_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(credentials_path, 0o600)
    return credentials_path


def _is_missing_user_error(error_message: str) -> bool:
    """Return whether WP-CLI failure indicates the user is absent."""
    normalized = error_message.lower()
    return "does not exist" in normalized or "invalid user id" in normalized


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Apply WordPress settings and cleanup defaults."""
    result = StageResult(name="settings", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )

        if dry_run:
            # Dry-run: just log intent
            pass
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for settings stage")
            applicator = SettingsApplicator(site_name, wp)
            applicator.cleanup_defaults()
            applicator.apply_settings(spec)

            email = spec.get("contact", {}).get("email")
            if not email:
                warning = "Skipping editor provisioning: contact.email not provided"
                logger.warning(warning)
                result.warnings.append(warning)
                credentials_path = _write_credentials_report(
                    build_dir,
                    {
                        "created": False,
                        "skipped": True,
                        "reason": "missing_contact_email",
                    },
                )
                result.artifacts_written.append(str(credentials_path))
                return result

            username = _derive_editor_username(email)
            get_user_command = f"user get {username} --format=json"
            credentials_payload: dict[str, str | bool] = {
                "username": username,
                "email": email,
                "role": "editor",
            }

            try:
                wp.run(get_user_command)
            except RuntimeError as exc:
                error_message = str(exc)
                if not _is_missing_user_error(error_message):
                    raise

                password = secrets.token_urlsafe(16)
                wp.user_create(username=username, email=email, role="editor", password=password)
                credentials_payload.update(
                    {
                        "created": True,
                        "password": password,
                    }
                )
            else:
                credentials_payload.update(
                    {
                        "created": False,
                        "skipped": True,
                        "reason": "user_exists",
                    }
                )

            credentials_path = _write_credentials_report(build_dir, credentials_payload)
            result.artifacts_written.append(str(credentials_path))

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
