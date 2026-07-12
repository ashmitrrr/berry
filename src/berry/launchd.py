"""macOS launchd agent management for berry's background reminder checker."""

import shutil
import subprocess
import sys
from pathlib import Path

PLIST_LABEL = "com.berry.reminders"
AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
BERRY_STATE_DIR = Path.home() / ".berry"

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>Label</key>
\t<string>{label}</string>
\t<key>ProgramArguments</key>
\t<array>
\t\t<string>{berry_bin}</string>
\t\t<string>_check-reminders</string>
\t</array>
\t<key>StartInterval</key>
\t<integer>60</integer>
\t<key>RunAtLoad</key>
\t<true/>
\t<key>StandardOutPath</key>
\t<string>{log_path}</string>
\t<key>StandardErrorPath</key>
\t<string>{log_path}</string>
</dict>
</plist>
"""


def plist_path() -> Path:
    return AGENTS_DIR / f"{PLIST_LABEL}.plist"


def resolve_berry_binary() -> str:
    """Locate the installed berry binary at runtime."""
    found = shutil.which("berry")
    if found:
        return found
    # Fallback: sibling of the active Python interpreter (e.g. inside a venv)
    candidate = Path(sys.executable).parent / "berry"
    if candidate.exists():
        return str(candidate)
    return sys.argv[0]


def render_plist() -> str:
    return _PLIST_TEMPLATE.format(
        label=PLIST_LABEL,
        berry_bin=resolve_berry_binary(),
        log_path=str(BERRY_STATE_DIR / "daemon.log"),
    )


def install() -> tuple[bool, str]:
    """Write the plist and load the launchd agent.

    Returns (success, plist_path_or_error_message).
    """
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    BERRY_STATE_DIR.mkdir(parents=True, exist_ok=True)

    dest = plist_path()
    dest.write_text(render_plist())

    try:
        # Unload silently in case a stale agent is already registered.
        subprocess.run(["launchctl", "unload", str(dest)], capture_output=True)

        result = subprocess.run(
            ["launchctl", "load", "-w", str(dest)],
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return False, "launchctl not found — background install requires macOS"

    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip()
        return False, f"launchctl load failed: {err}"
    return True, str(dest)


def uninstall() -> tuple[bool, str]:
    """Unload and delete the launchd agent plist.

    Returns (success, plist_path_or_reason).
    """
    dest = plist_path()
    if not dest.exists():
        return False, "not installed"

    try:
        subprocess.run(["launchctl", "unload", "-w", str(dest)], capture_output=True)
    except (FileNotFoundError, OSError):
        return False, "launchctl not found — background install requires macOS"

    dest.unlink()
    return True, str(dest)
