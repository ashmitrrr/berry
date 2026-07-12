# Contributing to berry

Thanks for wanting to help out. berry is small on purpose, so even a
small contribution goes a long way.

## Getting set up

```sh
git clone https://github.com/ashmitrrr/berry
cd berry

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

That pulls in `ruff` and `pytest` alongside berry itself.

> [!NOTE]
> Keep your clone outside `~/Documents`, `~/Desktop`, or iCloud Drive.
> macOS blocks background services from reading files in those folders,
> and the `launchd` agent will silently fail to start if it can't read
> its own `.venv`. See the README for the full story.

## Before you start

For anything bigger than a small fix -- new commands, changes to the
mood engine, new install paths -- open an issue first to talk through
the approach. It avoids wasted work if the direction doesn't fit, and
it's the fastest way to get unblocked if something in the macOS-specific
plumbing (`ioreg`, `pmset`, `NSWorkspace`, `launchd`) isn't behaving how
you expect on your setup.

For small fixes (typos, docs, small bugs), just send the PR.

## Project layout

- `src/berry/` -- the package itself: sprites, mood logic, CLI commands,
  menu bar app, reminder daemon
- `scripts/` -- packaging and asset-generation helpers
- `tests/` -- unit tests, mostly mood/decay/parsing logic that doesn't
  need a real Mac to run
- Sprites live under `src/berry/assets/` -- see Assets below before
  touching these

## Style

- Run `ruff check .` before committing.
- Match the existing tone of the CLI output and error messages -- berry
  talks like a pet, not a system daemon. Error messages should still be
  clear about what actually went wrong.
- Type hints on new code where reasonable. Not strictly enforced
  everywhere yet, but new code should trend that way.

## Testing

```sh
pytest
```

Mood transitions, hunger decay, and reminder parsing (`"in 10m"`,
`"15:30"`, etc.) are the easiest things to unit test without a real Mac,
and that's what the current suite covers. Anything that touches
`launchd`, `pmset`, or actual sleep/wake needs to be tested by hand and
called out in your PR description -- CI can't exercise real system
sleep state.

## Assets

The base cat sprites are from the
[Pet Cats Pack](https://luizmelo.itch.io/pet-cat-pack) by LuizMelo (CC0),
recolored for berry. If you're adding new moods or frames, keep new art
CC0 or your own original work, and say so in the PR -- this keeps the
whole asset set license-clean.

## Sending a PR

1. Fork, branch off `main`, keep the PR focused on one thing.
2. Describe what changed and why, not just what files moved.
3. If it changes user-facing behavior (new command, new flag, changed
   mood trigger), update the README's command/mood tables in the same
   PR.
4. If you can't test something end-to-end (not on macOS, or don't have
   Full Disk Access set up), say so -- that's fine, just flag it so a
   maintainer can verify that part.

## Reporting bugs / requesting features

Use the issue templates -- they ask for the couple of details (macOS
version, install method, `berry --version`) that save the most
back-and-forth when diagnosing a system-level bug.

Thanks again for contributing -- even a "the README was confusing here"
issue is genuinely useful.
