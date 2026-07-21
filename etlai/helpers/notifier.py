"""Cross-platform native OS toast notifications."""

import platform
import subprocess


def notify(title: str, message: str, open_folder: str | None = None, timeout: int = 5) -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            _notify_macos(title, message, open_folder)
        elif system == "Windows":
            _notify_windows(title, message, open_folder, timeout)
    except Exception:
        pass


def _notify_macos(title: str, message: str, open_folder: str | None) -> None:
    script = f'display notification "{_escape_applescript(message)}" with title "{_escape_applescript(title)}"'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    if open_folder:
        subprocess.run(["open", open_folder], check=False, capture_output=True)


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _notify_windows(title: str, message: str, open_folder: str | None, timeout: int) -> None:
    launch_action = ""
    if open_folder:
        escaped_folder = open_folder.replace("'", "''")
        launch_action = f"\n    Start-Process explorer.exe '{escaped_folder}'"

    powershell_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode("{_escape_powershell(title)}")) > $null
    $textNodes.Item(1).AppendChild($template.CreateTextNode("{_escape_powershell(message)}")) > $null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ETLai").Show($toast){launch_action}
    """
    subprocess.run(["powershell", "-NoProfile", "-Command", powershell_script], check=False, capture_output=True)


def _escape_powershell(text: str) -> str:
    return text.replace('"', '`"').replace("'", "''")
