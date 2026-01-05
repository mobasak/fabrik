#!/bin/bash
# Fabrik Notification Hook - Notification
#
# Sends desktop notification when droid needs input.
# Works on Linux (notify-send) and WSL (powershell).

input=$(cat)
message=$(echo "$input" | jq -r '.message // "Droid needs your attention"')

# Try Linux notify-send first
if command -v notify-send &> /dev/null; then
  notify-send "Factory Droid" "$message" --icon=dialog-information 2>/dev/null || true
  exit 0
fi

# WSL: Use PowerShell for Windows notifications
if grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
  powershell.exe -Command "
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    \$template = '<toast><visual><binding template=\"ToastText02\"><text id=\"1\">Factory Droid</text><text id=\"2\">$message</text></binding></visual></toast>'
    \$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    \$xml.LoadXml(\$template)
    \$toast = [Windows.UI.Notifications.ToastNotification]::new(\$xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Droid').Show(\$toast)
  " 2>/dev/null || true
  exit 0
fi

# Fallback: just echo (visible in terminal)
echo "🔔 Droid: $message"
exit 0
