

def test_app_logs_command_removed() -> None:
    """`fabrik app-logs` was a dead Coolify-API command (Coolify retired 2026-05-30);
    removed 2026-08-25. It must NOT be registered — a dead body behind a live click
    decorator passes --help while failing at runtime (infra finding 01M0WNJD)."""
    from fabrik.cli import cli

    assert "app-logs" not in cli.commands, "the dead Coolify app-logs command must stay removed"
