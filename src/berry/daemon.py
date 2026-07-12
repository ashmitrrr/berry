"""Background reminder checker.

Runs as a small loop (intended to be launched via a macOS launchd
agent) that polls ~/.berry/reminders.json and fires a native macOS
notification, styled as the pet, when a reminder comes due. This is
what lets reminders reach you even if the terminal isn't open.
"""

import subprocess
import time
from pathlib import Path

from berry import popup, reminders
from berry.render import mood_frames
from berry.state import load_state

ASSETS_DIR = Path(__file__).parent / "assets"

CHECK_INTERVAL_SECONDS = 30

PET_LABEL = {
    "cat": "🐱",
    "penguin": "🐧",
    "turtle": "🐢",
}


def notify_macos(title: str, message: str) -> bool:
    """Fire a native macOS notification via osascript.

    AppleScript string literals only need double-quotes escaped;
    backslashes are escaped first so the escaping itself can't break.

    Returns False instead of raising if osascript isn't available
    (non-macOS platform) or the call otherwise fails, so a missing
    notification never crashes the daemon loop.
    """
    def _escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False)
        return True
    except (FileNotFoundError, OSError):
        return False


def check_once() -> int:
    """Check for due reminders, notify for each, mark them fired.

    Returns the number of reminders fired, so callers (tests, CLI)
    can verify behavior without needing to wait on the loop.
    """
    state = load_state()
    emoji = PET_LABEL.get(state.species, "🐾")
    alert_frames = mood_frames(ASSETS_DIR, state.species, "alert")
    sprite = alert_frames[0] if alert_frames else None
    due = reminders.due_reminders()
    for r in due:
        title = f"{emoji} {state.name}"
        message = r["text"]
        if not popup.show_popup(title, message, sprite):
            notify_macos(title=title, message=message)
        reminders.mark_fired(r["id"])
    return len(due)


def run_forever() -> None:
    """Foreground polling loop — manual/debug fallback only.

    The recommended path is ``berry install``, which registers a launchd
    agent that invokes ``berry _check-reminders`` once every 60 s without
    keeping a terminal open. Use this command when debugging notification
    behaviour or when launchd is unavailable.
    """
    while True:
        check_once()
        time.sleep(CHECK_INTERVAL_SECONDS)
