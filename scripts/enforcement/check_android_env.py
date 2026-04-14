#!/usr/bin/env python3
"""
Verify WSL-to-Windows Android SDK communication.
Ensures ANDROID_HOME is set and reachable across the mount.
"""

import os
import shutil
import sys
from pathlib import Path


def check_android_env() -> bool:
    """Verify Android development environment is accessible from WSL."""

    # 1. Check Environment Variable
    android_home = os.getenv("ANDROID_HOME")
    if not android_home:
        print("FAIL: ANDROID_HOME environment variable is not set.")
        print(
            "Tip: Add 'export ANDROID_HOME=/mnt/c/Users/YourUser/AppData/Local/Android/Sdk'"
            " to ~/.bashrc"
        )
        return False

    # 2. Verify Path Accessibility (WSL Mount)
    sdk_path = Path(android_home)
    if not sdk_path.exists():
        print(f"FAIL: Android SDK path not found: {android_home}")
        print("Tip: Ensure your Windows C: drive is mounted in WSL at /mnt/c")
        return False

    # 3. Check for ADB Presence
    adb_windows = sdk_path / "platform-tools" / "adb.exe"
    adb_wsl = shutil.which("adb")

    if not adb_windows.exists() and not adb_wsl:
        print("FAIL: adb.exe not found in platform-tools and adb not in WSL PATH.")
        print("Tip: Install Android SDK Platform Tools via Android Studio")
        return False

    print(f"PASS: Android Environment verified at {android_home}")

    # 4. Optional: Check for emulator
    emulator_path = sdk_path / "emulator" / "emulator.exe"
    if emulator_path.exists():
        print("  ✓ Android Emulator found")
    else:
        print("  ⚠ Android Emulator not found (optional)")

    return True


if __name__ == "__main__":
    sys.exit(0 if check_android_env() else 1)
