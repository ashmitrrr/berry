# Task: turn berry into an always-visible, AI-aware desktop companion

You're working in the `berry` repo, on branch `berry-upgd` (branched fresh
from `main` -- it does NOT contain the hover-to-expand notch panel work,
which is intentionally parked on a separate branch, `version-0.2.0`, and
out of scope here. Don't port it over or reference its design as the
thing to build -- it's a different interaction model than what this task
asks for).

## Read this first

- `README.md` -- what berry is and the philosophy: "no accounts, no
  server, no Electron -- just a `.venv` and your Mac." Any feature you
  add has to respect that, or make the exception a deliberate, opt-in,
  clearly-documented choice, not a silent default.
- `CONTRIBUTING.md` -- project conventions: `ruff check .` before
  committing, pure-logic code gets unit tests (mood/decay/parsing are
  the existing examples), anything touching `launchd`/`pmset`/real
  sleep-wake/AppKit windows needs hand-verification on a real Mac and
  should be flagged as such in your PR description, since CI and most
  sandboxes can't exercise real display/window state.
- `src/berry/state.py` -- the mood engine (hunger decay, mood
  transitions from real CPU/idle telemetry). This is pure logic, fully
  unit-tested, and should NOT need to change for this task. Reuse it,
  don't reimplement it.
- `src/berry/render.py` -- sprite helpers: `mood_frames()` returns the
  frame list for a species+mood, `menubar_frame()` returns the tiny
  cropped icon variant. For this task you want the *full-res* frames
  `mood_frames()` returns, not the menubar crop -- the whole point is
  bigger.
- `src/berry/popup.py` -- the existing pattern for a borderless,
  non-activating, floating `NSPanel` (used today for the reminder
  popup). This is your reference for how berry already does floating
  windows: `NSWindowStyleMaskNonactivatingPanel` (mask value 128),
  `NSFloatingWindowLevel`, transparent background, wrapped in
  try/except so any AppKit failure degrades to a silent no-op rather
  than crashing the app. Follow this defensive pattern for every new
  panel you add.
- `src/berry/cli.py`, the `menubar()` command -- this is where
  `rumps.App` (`BerryMenuBar`) lives today: the animation timer, the
  CPU-reactive mood sync, and the wake-from-sleep observer
  (`NSWorkspaceDidWakeNotification`, see `_on_wake`). That wake observer
  is exactly the hook point for the "greets you when you open your Mac"
  feature below -- don't build a new wake-detection mechanism, reuse
  this one.

## What to build

### 1. Always-visible, bigger companion (do this part first)

Right now berry only exists as a ~20-40px menu bar icon. The ask is a
persistent floating companion -- inspired explicitly by the "Googly
Eyes" menu bar app, which is always on screen, not hidden in a dropdown
and not gated behind any interaction. Berry should get the same
treatment: a borderless floating panel (same technique as
`popup.py`/the parked notch work, but *not* hover-gated -- visible by
default, all the time), sized noticeably bigger than the current menu
bar icon (start around 100-140px sprite size and adjust from there),
showing the live mood animation exactly as it works today (idle,
happy, hungry, running, sleeping -- driven by the same
`state.py`/`render.py` you're already reusing).

Things to decide and document your reasoning for, since there's no
existing precedent in this codebase to copy:
- Where it sits on screen by default (top-center under the menu bar is
  a reasonable default, matching the parked notch experiment, but it
  should probably be configurable eventually -- at minimum leave a
  clear seam for that, don't hardcode assumptions everywhere).
- Whether it should be draggable/repositionable by the user, or fixed.
  Fixed-for-now is fine, but say so explicitly rather than silently
  deciding.
- How `berry menubar` and this new always-on companion relate -- are
  they the same command now, or does the always-on companion replace
  the menu bar icon, or do both coexist? Pick one and be explicit about
  it in the README update.

Keep this fully offline and dependency-free, exactly like everything
else in berry today. This part should ship and be testable/reviewable
completely on its own, independent of part 2.

### 2. Wake-triggered AI check-in

When the Mac wakes from sleep (reuse the existing
`NSWorkspaceDidWakeNotification` observer already wired up in
`BerryMenuBar`), berry should proactively greet the user -- something
like "hey, how are you doing?" -- and accept a free-form typed reply,
then respond in berry's voice using an LLM.

This needs three new pieces, and they're genuinely separable -- build
and test them independently rather than as one tangled feature:

**a. An interactive floating panel.** Every panel berry has today
(`popup.py`, the parked notch work) explicitly calls
`setIgnoresMouseEvents_(True)` and is a non-activating panel that never
takes keyboard focus -- that's why they're safe to leave floating over
whatever the user is doing. A chat input needs the opposite: a
focusable `NSTextField` the user can actually type into and submit
(Enter key). This is new territory for berry -- there's no existing
pattern to copy, so keep it as narrowly scoped as possible: focus
should be requested only while the input is actively shown, and
released the moment a reply is submitted or the panel is dismissed, so
it behaves like a brief prompt, not a window that steals your keyboard
indefinitely.

**b. A pluggable "AI backend."** Do not hardcode a single provider.
Design a small interface (something like a `Backend` protocol/ABC with
a `reply(prompt: str, context: dict) -> str` method) with at least:
  - A **local backend** using Ollama's local HTTP API (`localhost:11434`
    by default) if the user has it installed -- this is the one that
    keeps berry's "no accounts, no server" promise fully intact, since
    nothing leaves the machine. This should be the default/recommended
    path in the README.
  - Optionally, an **API-key backend** (Anthropic or OpenAI) for users
    who want a sharper conversational partner and are fine with an
    opt-in exception to the offline promise. The key must be
    user-supplied and stored in a local config file, never bundled,
    never required, never sent anywhere except directly to that
    provider's API.
  - If neither is configured, the check-in feature should simply not
    fire -- degrade silently, don't error, don't nag. berry should work
    exactly as it does today for anyone who doesn't opt into this.

  This almost certainly means introducing berry's first real config
  file (something like `~/.berry/config.json`) since there's currently
  no user-facing settings surface in the codebase at all -- check
  `state.py`'s `~/.berry/state.json` handling for the existing pattern
  of where berry keeps its local data, and follow the same convention
  (same directory, same JSON-on-disk approach, same defensive
  load/missing-file handling).

**c. berry's reply voice.** Keep responses short, warm, a little
whimsical -- in keeping with "berry talks like a pet, not a system
daemon" from CONTRIBUTING.md. This is a casual daily check-in, not a
chat assistant and not a therapy substitute -- don't have berry give
advice, diagnose, or engage deeply with anything that sounds like real
emotional distress; a simple sympathetic pet-appropriate response and
moving on is the right register. If you want to bake in one hard rule,
make it that one.

## Constraints

- **Do not auto-commit anything.** Stage changes if that's your normal
  workflow, but leave the actual `git commit` to the user to review and
  run themselves.
- Keep `ruff check .` clean and add unit tests for anything that's pure
  logic (config load/save, the backend interface's non-AppKit parts,
  any parsing). Anything that touches real AppKit windows or an actual
  wake/sleep cycle can't be meaningfully unit tested -- say so plainly
  in your PR description instead of skipping silently, per
  CONTRIBUTING.md's existing convention for launchd/pmset code.
- Update the README's command table and "How it works" section for
  whatever you ship -- that's an existing project convention, not new
  process.
- Ship part 1 (always-visible bigger companion) as a reviewable unit
  before building part 2 on top of it. Don't build the chat feature
  against a moving target.
