"""Background reminder checker.

Runs as a small loop (intended to be launched via a macOS launchd
agent) that polls ~/.berry/reminders.json and fires a native macOS
notification, styled as the pet, when a reminder comes due. This is
what lets reminders reach you even if the terminal isn't open.
"""

import subprocess
import time

from berry import reminders
from berry.state import load_state

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
    due = reminders.due_reminders()
    for r in due:
        notify_macos(
            title=f"{emoji} {state.name}",
            message=r["text"],
        )
        reminders.mark_fired(r["id"])
    return len(due)


def run_forever() -> None:
    """Foreground polling loop. This is what the launchd agent runs."""
    while True:
        check_once()
        time.sleep(CHECK_INTERVAL_SECONDS)
