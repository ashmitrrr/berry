"""Floating "notch" panel: a bigger, hover-to-expand version of berry.

The actual macOS menu bar caps icon height at roughly 22pt (44px @2x) --
that's an OS rule, not something berry can work around. So instead of
trying to make the menu bar icon itself bigger, this renders a separate
borderless floating panel pinned top-center of the screen, right where
the menu bar ends, and pops it open on hover to show berry much larger.

This is the same trick apps like Boring Notch / NotchNook use to fake a
Dynamic-Island-style widget even on Macs with no physical notch: a
rounded, mostly-black capsule tucked under the menu bar reads as "part
of the bezel" whether or not there's an actual notch cut into the
screen there.

Everything AppKit-related is wrapped in try/except at construction time.
If it fails for any reason (no display, PyObjC missing, screen API
shape changes), `self.ok` stays False and every method becomes a no-op
-- the menu bar keeps working exactly as it did before this existed.
"""

from pathlib import Path
from typing import Any

_PANEL_W = 160
_PANEL_H = 92
_SPRITE_SIZE = 72
_SPRITE_MARGIN_TOP = 10
_CORNER_RADIUS = 22.0
_LABEL_H = 16
# Style mask: 128 = NSWindowStyleMaskNonactivatingPanel (borderless panel
# that never steals key-window status from the current foreground app).
_PANEL_STYLE = 128


def point_in_rect(
    px: float,
    py: float,
    rx: float,
    ry: float,
    rw: float,
    rh: float,
    margin: float = 0.0,
) -> bool:
    """True if (px, py) falls within the rect, grown by `margin` on each side.

    A small margin gives hover detection some slack so cursor jitter
    right at the icon's edge doesn't flicker the panel open and closed.
    Pure arithmetic -- no AppKit needed -- so it's unit-testable on any OS.
    """
    return (
        rx - margin <= px <= rx + rw + margin
        and ry - margin <= py <= ry + rh + margin
    )


def find_status_button(app: Any) -> Any | None:
    """Best-effort lookup of the underlying NSStatusBarButton for a rumps.App.

    rumps doesn't publicly expose the NSStatusItem it creates, so this
    tries a few attribute paths seen across rumps versions. If none of
    them work (rumps internals changed, app isn't a rumps.App, etc.)
    this returns None and hover detection simply stays inactive --
    the rest of the menu bar app is unaffected.
    """
    candidates = (
        lambda a: a._nsapp.nsstatusitem.button(),
        lambda a: a.nsstatusitem.button(),
        lambda a: a._status_item.button(),
    )
    for candidate in candidates:
        try:
            button = candidate(app)
            if button is not None:
                return button
        except Exception:
            continue
    return None


class NotchPanel:
    """A persistent, reusable floating panel.

    Construct once and call `show()` / `hide()` / `set_frame()`
    repeatedly from the menu bar's existing timers -- rebuilding the
    window on every hover would flicker and leak.
    """

    def __init__(self) -> None:
        self.ok = False
        self._visible = False
        try:
            from AppKit import (
                NSApplication,
                NSApplicationActivationPolicyAccessory,
                NSBackingStoreBuffered,
                NSBox,
                NSColor,
                NSFloatingWindowLevel,
                NSFont,
                NSImage,
                NSImageScaleProportionallyUpOrDown,
                NSImageView,
                NSPanel,
                NSScreen,
                NSTextField,
            )
            from Foundation import NSMakeRect

            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

            screen = NSScreen.mainScreen()
            if screen is None:
                return

            # visibleFrame() excludes the menu bar; frame() includes it.
            # Anchoring the panel's top edge to visibleFrame's top edge
            # means it starts exactly where the menu bar ends -- like a
            # shade hanging down from it.
            vf = screen.visibleFrame()
            sf = screen.frame()
            x = sf.origin.x + (sf.size.width - _PANEL_W) / 2
            y = vf.origin.y + vf.size.height - _PANEL_H

            panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(x, y, _PANEL_W, _PANEL_H),
                _PANEL_STYLE,
                NSBackingStoreBuffered,
                False,
            )
            panel.setLevel_(NSFloatingWindowLevel)
            panel.setHasShadow_(True)
            panel.setOpaque_(False)
            panel.setBackgroundColor_(NSColor.clearColor())
            panel.setIgnoresMouseEvents_(True)

            # NSBox gives a rounded-rect fill via NSColor directly --
            # same approach as popup.py, avoids CGColor bridging quirks.
            box = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, _PANEL_W, _PANEL_H))
            box.setBoxType_(4)  # NSBoxCustom
            box.setFillColor_(
                NSColor.colorWithSRGBRed_green_blue_alpha_(0.08, 0.08, 0.09, 0.92)
            )
            box.setBorderWidth_(0)
            box.setCornerRadius_(_CORNER_RADIUS)
            cv = box.contentView()

            sprite_x = (_PANEL_W - _SPRITE_SIZE) // 2
            sprite_y = _PANEL_H - _SPRITE_SIZE - _SPRITE_MARGIN_TOP
            iv = NSImageView.alloc().initWithFrame_(
                NSMakeRect(sprite_x, sprite_y, _SPRITE_SIZE, _SPRITE_SIZE)
            )
            iv.setImageScaling_(NSImageScaleProportionallyUpOrDown)
            cv.addSubview_(iv)

            label = NSTextField.alloc().initWithFrame_(
                NSMakeRect(0, 6, _PANEL_W, _LABEL_H)
            )
            label.setEditable_(False)
            label.setSelectable_(False)
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setAlignment_(1)  # NSTextAlignmentCenter
            label.setFont_(NSFont.systemFontOfSize_(11.0))
            label.setTextColor_(
                NSColor.colorWithSRGBRed_green_blue_alpha_(0.85, 0.85, 0.87, 1.0)
            )
            cv.addSubview_(label)

            panel.setContentView_(box)

            self._panel = panel
            self._image_view = iv
            self._label = label
            self._NSImage = NSImage
            self.ok = True
        except Exception:
            self.ok = False

    def set_frame(self, sprite_path: Path, label_text: str = "") -> None:
        """Update the sprite image and label without touching visibility."""
        if not self.ok:
            return
        try:
            ns_img = self._NSImage.alloc().initWithContentsOfFile_(str(sprite_path))
            if ns_img is not None:
                self._image_view.setImage_(ns_img)
            if label_text:
                self._label.setStringValue_(label_text)
        except Exception:
            pass

    def show(self) -> None:
        if not self.ok or self._visible:
            return
        try:
            self._panel.orderFrontRegardless()
            self._visible = True
        except Exception:
            pass

    def hide(self) -> None:
        if not self.ok or not self._visible:
            return
        try:
            self._panel.orderOut_(None)
            self._visible = False
        except Exception:
            pass

    @property
    def visible(self) -> bool:
        return self._visible
