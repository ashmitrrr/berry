"""berry CLI - `berry status`, `berry feed`, `berry remind ...`."""

import subprocess
import time
from pathlib import Path

import click
from rich.console import Console

from berry import __version__, reminders
from berry.daemon import run_forever
from berry.render import menubar_frame, mood_frames, render_sprite
from berry.state import feed as feed_state
from berry.state import nap as nap_state
from berry.state import wake as wake_state
from berry.state import load_state, mood, save_state, touch
from berry.state import apply_decay as decay_state

console = Console()
ASSETS_DIR = Path(__file__).parent / "assets"

MOOD_FALLBACK_EMOJI = {
    "idle": "( =^-^= )",
    "happy": "( =^‥^= )",
    "hungry": "( =`ェ´= )  hungry...",
    "sleeping": "( =-‥-= )  zzz",
    "alert": "( =O‥O= )  !",
}


def _first_frame_path(species: str, pet_mood: str) -> Path | None:
    """Return path to frame_01.png for the mood folder, or None."""
    frames = mood_frames(ASSETS_DIR, species, pet_mood)
    return frames[0] if frames else None


def _render(species: str, pet_mood: str) -> None:
    """Render the pet's first frame, or a text placeholder if no frames exist."""
    frame = _first_frame_path(species, pet_mood)
    if frame:
        console.print(render_sprite(frame))
    else:
        placeholder = MOOD_FALLBACK_EMOJI.get(pet_mood, "( =^..^= )")
        console.print(f"  {placeholder}")
        console.print(
            f"  [dim](no frames for {species}/{pet_mood} yet)[/dim]"
        )


def _load_current_state():
    state = load_state()
    state = decay_state(state)
    save_state(state)
    return state


@click.group()
@click.version_option(__version__, prog_name="berry")
def main() -> None:
    """berry - a cute terminal pet that reminds you of things."""


@main.command()
def status() -> None:
    """Show your pet and its current mood."""
    state = _load_current_state()
    current_mood = mood(state)
    _render(state.species, current_mood)
    console.print(
        f"\n[bold]{state.name}[/bold] the {state.species} "
        f"— {current_mood}, hunger {int(state.hunger)}/100"
    )

    due = reminders.due_reminders()
    if due:
        console.print(f"\n[yellow]{state.name} has {len(due)} reminder(s) for you![/yellow]")
        for r in due:
            console.print(f"  • {r['text']}")
            reminders.mark_fired(r["id"])

    upcoming = reminders.pending_reminders()
    if upcoming:
        console.print(f"\n[dim]{len(upcoming)} reminder(s) still pending. See `berry reminders`.[/dim]")


@main.command()
def feed() -> None:
    """Feed your pet."""
    state = _load_current_state()
    state = feed_state(state)
    _render(state.species, mood(state))
    console.print(f"\n[green]{state.name} is full and happy![/green]")


@main.command()
def nap() -> None:
    """Put your pet to sleep and send the Mac to sleep."""
    state = _load_current_state()
    state = nap_state(state)
    _render(state.species, "sleeping")
    console.print(f"\n[dim]{state.name} curls up... goodnight.[/dim]")
    try:
        subprocess.run(["pmset", "sleepnow"], check=False)
    except (FileNotFoundError, OSError):
        console.print(
            "[yellow](pmset not available — pet is sleeping but Mac stays awake)[/yellow]"
        )


@main.command()
def wake() -> None:
    """Wake your pet up from a manual nap.

    Only needed if you used ``berry nap`` without ``berry menubar``
    running — the menu bar app clears this automatically when it
    detects the Mac waking up. This is the manual fallback.
    """
    state = load_state()
    state = wake_state(state)
    current_mood = mood(state)
    _render(state.species, current_mood)
    console.print(f"\n[green]{state.name} stretches and wakes up![/green]")


@main.command()
@click.argument("text")
@click.argument("when")
def remind(text: str, when: str) -> None:
    """Set a reminder. WHEN can be 'in 10m', 'in 2h', or '15:30'."""
    state = _load_current_state()
    touch(state)
    try:
        due_at = reminders.parse_when(when)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    reminders.add_reminder(text, due_at)
    console.print(
        f"[green]Got it — {state.name} will remind you: "
        f"\"{text}\" at {due_at.strftime('%H:%M')}[/green]"
    )


@main.command(name="reminders")
def list_reminders() -> None:
    """List all pending reminders."""
    upcoming = reminders.pending_reminders()
    if not upcoming:
        console.print("[dim]No pending reminders.[/dim]")
        return
    for r in upcoming:
        from datetime import datetime

        due = datetime.fromtimestamp(r["due_at"]).strftime("%a %H:%M")
        console.print(f"  [cyan]{due}[/cyan]  {r['text']}")


@main.command()
def daemon() -> None:
    """Run the reminder checker in the foreground (debug/manual fallback).

    The normal background path is ``berry install``, which registers a
    launchd agent that wakes once per minute without a terminal open.
    Use this only for debugging or on non-macOS systems.
    """
    console.print("[dim]berry daemon running — checking reminders every 30s. Ctrl+C to stop.[/dim]")
    run_forever()


@main.command(name="_check-reminders", hidden=True)
def check_reminders() -> None:
    """One-shot reminder check — invoked by launchd every 60 s."""
    from berry.daemon import check_once
    check_once()


@main.command()
def install() -> None:
    """Install berry as a macOS background service (launchd agent)."""
    from berry import launchd
    ok, msg = launchd.install()
    if ok:
        console.print("[green]berry installed as a background service.[/green]")
        console.print(f"[dim]Plist: {msg}[/dim]")
        console.print("[dim]Reminders will be checked every 60 seconds automatically.[/dim]")
    else:
        console.print(f"[red]Install failed: {msg}[/red]")
        raise SystemExit(1)


@main.command()
def uninstall() -> None:
    """Remove berry from macOS background services (launchd agent)."""
    from berry import launchd
    ok, msg = launchd.uninstall()
    if ok:
        console.print("[green]berry background service removed.[/green]")
        console.print(f"[dim]Removed: {msg}[/dim]")
    else:
        if msg == "not installed":
            console.print("[yellow]berry is not currently installed as a background service.[/yellow]")
        else:
            console.print(f"[red]Uninstall failed: {msg}[/red]")
            raise SystemExit(1)


@main.command()
@click.option("--fps", default=9, show_default=True, help="Frames per second.")
def watch(fps: int) -> None:
    """Watch your pet animate live. Ctrl+C to stop."""
    from rich.live import Live
    from rich.text import Text

    # animation redraws at `fps`, but hunger/mood only meaningfully
    # change over minutes — reload state once a second, not every frame.
    STATE_CHECK_INTERVAL = 1.0
    frame_delay = 1.0 / max(1, fps)

    try:
        with Live(console=console, refresh_per_second=fps, screen=False) as live:
            frame_index = 0
            current_mood = None
            frames: list[Path] = []
            state = None
            last_state_check = 0.0

            while True:
                now = time.monotonic()
                if state is None or now - last_state_check >= STATE_CHECK_INTERVAL:
                    state = load_state()
                    state = decay_state(state)
                    save_state(state)
                    last_state_check = now

                    new_mood = mood(state)
                    if new_mood != current_mood:
                        current_mood = new_mood
                        frames = mood_frames(ASSETS_DIR, state.species, current_mood)
                        frame_index = 0

                if frames:
                    frame_path = frames[frame_index % len(frames)]
                    rendered = render_sprite(frame_path)
                    status_line = Text(
                        f"\n{state.name} — {current_mood}, hunger {int(state.hunger)}/100"
                        "  [Ctrl+C to stop]",
                        style="dim",
                    )
                    rendered.append_text(status_line)
                    live.update(rendered)
                    frame_index += 1
                else:
                    placeholder = MOOD_FALLBACK_EMOJI.get(current_mood, "( =^..^= )")
                    live.update(Text(f"  {placeholder}\n  [dim](no frames)[/dim]"))

                time.sleep(frame_delay)
    except KeyboardInterrupt:
        pass


@main.command()
@click.option("--fps", default=4, show_default=True, help="Icon animation frames per second.")
@click.option(
    "--companion/--no-companion",
    default=True,
    show_default=True,
    help="Also show berry as a floating companion on your desktop.",
)
def menubar(fps: int, companion: bool) -> None:
    """Run berry as an animated macOS menu bar app."""
    try:
        import rumps
    except ImportError:
        raise click.ClickException(
            "rumps is required for the menu bar: pip install rumps"
        )
    import psutil

    from berry.ai import backend_from_config
    from berry.checkin import due_for_checkin, show_checkin
    from berry.companion import create_companion
    from berry.config import load_config

    # Try to set up the PyObjC wake-notification class once per invocation.
    # Wrapping everything in except Exception means non-macOS / missing PyObjC
    # simply leaves these as None and the observer setup in __init__ is skipped.
    _WakeObserver = None
    _wake_nc = None
    try:
        from Foundation import NSObject as _NSObject
        from AppKit import NSWorkspace as _NSWorkspace

        class _WakeObserver(_NSObject):
            def handleWake_(self, _notification):
                cb = getattr(self, "_berry_callback", None)
                if cb is not None:
                    cb()

        _wake_nc = _NSWorkspace.sharedWorkspace().notificationCenter()
    except Exception:
        pass

    # Capture module-level names for the closure so the nested class
    # doesn't need to qualify every reference.
    _mood_frames = mood_frames
    _menubar_frame = menubar_frame
    _load_state = load_state
    _decay_state = decay_state
    _save_state = save_state
    _mood = mood
    _feed_state = feed_state
    _wake_state = wake_state
    _assets = ASSETS_DIR
    _psutil = psutil
    _create_companion = create_companion
    _backend_from_config = backend_from_config
    _due_for_checkin = due_for_checkin
    _show_checkin = show_checkin
    _load_config = load_config
    _first_frame = _first_frame_path

    class BerryMenuBar(rumps.App):
        def __init__(self):
            state = _load_state()
            state = _decay_state(state)
            _save_state(state)
            self._state = state
            cpu = _psutil.cpu_percent(interval=None)
            self._current_mood = _mood(state, cpu_percent=cpu)
            self._frames = _mood_frames(_assets, state.species, self._current_mood)
            self._frame_index = 0

            initial_icon = str(_menubar_frame(self._frames[0])) if self._frames else None
            super().__init__(
                name="berry",
                icon=initial_icon,
                template=False,
                menu=["Feed", "Status"],
            )
            # Explicitly disable template mode so macOS renders full color
            # instead of flattening the pixel art to a black silhouette.
            if initial_icon:
                self.template = False

            # Floating desktop companion — shows the same animation at
            # full sprite size. None if disabled or the panel can't be
            # created (no display, etc.); the icon works without it.
            self._companion = _create_companion() if companion else None
            self._last_checkin = 0.0

            rumps.Timer(self._next_frame, 1.0 / max(1, fps)).start()
            rumps.Timer(self._sync_state, 4.0).start()

            self._wake_observer = None
            if _WakeObserver is not None and _wake_nc is not None:
                try:
                    obs = _WakeObserver.alloc().init()
                    obs._berry_callback = self._on_wake
                    self._wake_observer = obs
                    _wake_nc.addObserver_selector_name_object_(
                        obs, "handleWake:", "NSWorkspaceDidWakeNotification", None
                    )
                except Exception:
                    pass

        def _on_wake(self):
            state = _load_state()
            _wake_state(state)   # clears manual_sleep, resets last_interaction, saves
            self._sync_state(None)
            self._maybe_checkin()

        def _maybe_checkin(self):
            # AI check-in is opt-in: backend_from_config returns None
            # unless the user configured one in ~/.berry/config.json,
            # and then wake behaves exactly as it always has.
            try:
                now = time.time()
                if not _due_for_checkin(self._last_checkin, now):
                    return
                backend = _backend_from_config(_load_config())
                if backend is None:
                    return
                cpu = _psutil.cpu_percent(interval=None)
                context = {
                    "name": self._state.name,
                    "mood": _mood(self._state, cpu_percent=cpu),
                    "hunger": int(self._state.hunger),
                }
                sprite = _first_frame(self._state.species, "alert") or _first_frame(
                    self._state.species, "idle"
                )
                if _show_checkin(backend, context, sprite_path=sprite):
                    self._last_checkin = now
            except Exception:
                pass

        def _next_frame(self, _sender):
            if not self._frames:
                return
            frame = self._frames[self._frame_index % len(self._frames)]
            self.icon = str(_menubar_frame(frame))
            if self._companion is not None:
                self._companion.set_frame(frame)
            # Re-apply after each swap — NSImage objects reset template state
            # when assigned, so setting it once in __init__ is not enough.
            self.template = False
            self._frame_index += 1

        def _sync_state(self, _sender):
            state = _load_state()
            state = _decay_state(state)
            _save_state(state)
            self._state = state
            cpu = _psutil.cpu_percent(interval=None)
            new_mood = _mood(state, cpu_percent=cpu)
            if new_mood != self._current_mood:
                self._current_mood = new_mood
                self._frames = _mood_frames(_assets, state.species, new_mood)
                self._frame_index = 0

        @rumps.clicked("Feed")
        def on_feed(self, _sender):
            self._state = _feed_state(self._state)
            cpu = _psutil.cpu_percent(interval=None)
            new_mood = _mood(self._state, cpu_percent=cpu)
            if new_mood != self._current_mood:
                self._current_mood = new_mood
                self._frames = _mood_frames(_assets, self._state.species, new_mood)
                self._frame_index = 0

        @rumps.clicked("Status")
        def on_status(self, _sender):
            cpu = _psutil.cpu_percent(interval=None)
            current_mood = _mood(self._state, cpu_percent=cpu)
            rumps.notification(
                title=f"{self._state.name} the {self._state.species}",
                subtitle=f"Mood: {current_mood}",
                message=f"Hunger: {int(self._state.hunger)}/100",
            )

    BerryMenuBar().run()


if __name__ == "__main__":
    main()
