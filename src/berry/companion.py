"""Always-visible floating companion: berry as a big sprite on your desktop.

Unlike the reminder popup (popup.py), this panel is long-lived: it stays
up for the whole `berry menubar` session and gets its image swapped by
the menu bar app's existing animation timer -- there's no run loop or
timer of its own here.

Same defensive AppKit pattern as popup.py: creation returns None and
every method is a silent no-op on failure, so the menu bar icon keeps
working even when the panel can't (no display, missing PyObjC, ...).

The panel ignores mouse events entirely (click-through) and never takes
keyboard focus, so it can float over whatever you're doing without
getting in the way. Position is fixed at top-center just under the menu
bar; it's computed in one place (panel_origin) so a user-configurable
position later is a one-line change, not a refactor.
"""

from __future__ import annotations

import io
from pathlib import Path

SPRITE_SIZE = 120
# Style mask: 128 = NSWindowStyleMaskNonactivatingPanel (see popup.py).
_PANEL_STYLE = 128
# Collection behavior: canJoinAllSpaces (1) | stationary (16) -- the
# companion follows you across Spaces instead of living on one desktop.
_COLLECTION_BEHAVIOR = 1 | 16


def scaled_size(width: int, height: int, target: int) -> tuple[int, int]:
    """Scale (width, height) so the longer side equals target, keeping ratio."""
    if width <= 0 or height <= 0:
        return (target, target)
    scale = target / max(width, height)
    return (max(1, round(width * scale)), max(1, round(height * scale)))


def panel_origin(
    screen_x: float,
    screen_y: float,
    screen_w: float,
    screen_h: float,
    panel_w: float,
    panel_h: float,
) -> tuple[float, float]:
    """Bottom-left origin that puts the panel top-center of the visible area.

    visibleFrame already excludes the menu bar, so "top of visible area"
    means directly underneath it.
    """
    x = screen_x + (screen_w - panel_w) / 2
    y = screen_y + screen_h - panel_h
    return (x, y)


def _load_scaled_image(frame_path: Path, sprite_size: int):
    """Return an NSImage of the frame pre-scaled with Pillow, or None.

    NSImageView's own scaling linearly interpolates, which smears pixel
    art -- so scale with NEAREST first, at 2x pixels with a 1x point
    size, matching the existing @2x menubar-icon convention for crisp
    rendering on retina displays.
    """
    try:
        from AppKit import NSImage
        from Foundation import NSData, NSMakeSize
        from PIL import Image

        img = Image.open(frame_path).convert("RGBA")
        px_w, px_h = scaled_size(img.width, img.height, sprite_size * 2)
        img = img.resize((px_w, px_h), Image.NEAREST)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()
        data = NSData.dataWithBytes_length_(raw, len(raw))
        ns_img = NSImage.alloc().initWithData_(data)
        if ns_img is None:
            return None
        ns_img.setSize_(NSMakeSize(px_w / 2, px_h / 2))
        return ns_img
    except Exception:
        return None


class CompanionPanel:
    """Long-lived floating sprite panel. Create via create_companion()."""

    def __init__(self, panel, image_view, sprite_size: int):
        self._panel = panel
        self._image_view = image_view
        self._sprite_size = sprite_size
        self._image_cache: dict[Path, object] = {}

    def set_frame(self, frame_path: Path) -> None:
        """Swap the displayed sprite frame. Silent no-op on any failure."""
        try:
            image = self._image_cache.get(frame_path)
            if image is None:
                image = _load_scaled_image(frame_path, self._sprite_size)
                if image is None:
                    return
                self._image_cache[frame_path] = image
            self._image_view.setImage_(image)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._panel.close()
        except Exception:
            pass


def create_companion(sprite_size: int = SPRITE_SIZE) -> CompanionPanel | None:
    """Build and show the floating companion panel.

    Returns None on any failure so the caller can simply skip companion
    updates -- same contract as popup.show_popup().
    """
    try:
        from AppKit import (
            NSBackingStoreBuffered,
            NSColor,
            NSFloatingWindowLevel,
            NSImageScaleProportionallyUpOrDown,
            NSImageView,
            NSPanel,
            NSScreen,
        )
        from Foundation import NSMakeRect

        screen = NSScreen.mainScreen()
        if screen is None:
            return None

        vf = screen.visibleFrame()
        x, y = panel_origin(
            vf.origin.x,
            vf.origin.y,
            vf.size.width,
            vf.size.height,
            sprite_size,
            sprite_size,
        )

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, sprite_size, sprite_size),
            _PANEL_STYLE,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        # The sprite has transparent edges; a rectangular shadow would
        # outline the invisible panel bounds instead of the cat.
        panel.setHasShadow_(False)
        panel.setIgnoresMouseEvents_(True)
        panel.setCollectionBehavior_(_COLLECTION_BEHAVIOR)

        image_view = NSImageView.alloc().initWithFrame_(
            NSMakeRect(0, 0, sprite_size, sprite_size)
        )
        image_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        panel.setContentView_(image_view)
        panel.orderFrontRegardless()

        return CompanionPanel(panel, image_view, sprite_size)
    except Exception:
        return None
