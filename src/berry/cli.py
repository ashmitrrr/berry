"""berry CLI - `berry status`, `berry feed`, `berry remind ...`."""

import time
from pathlib import Path

import click
from rich.console import Console

from berry import reminders
from berry.daemon import run_forever
from berry.render import mood_frames, render_sprite
from berry.state import feed as feed_state
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
    """Run the background reminder checker in the foreground (for testing).

    In production this is what a launchd agent runs continuously so
    reminders fire as native notifications even when no terminal is open.
    """
    console.print("[dim]berry daemon running — checking reminders every 30s. Ctrl+C to stop.[/dim]")
    run_forever()


@main.command()
@click.option("--fps", default=9, show_default=True, help="Frames per second.")
def watch(fps: int) -> None:
    """Watch your pet animate live. Ctrl+C to stop."""
    from rich.live import Live
    from rich.text import Text

    frame_delay = 1.0 / max(1, fps)

    try:
        with Live(console=console, refresh_per_second=fps, screen=False) as live:
            frame_index = 0
            current_mood = None
            frames: list[Path] = []

            while True:
                state = load_state()
                state = decay_state(state)
                save_state(state)
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


if __name__ == "__main__":
    main()
