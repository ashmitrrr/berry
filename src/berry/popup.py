"""Floating reminder popup: berry sprite + speech-bubble-style message.

Displayed by the daemon when a reminder fires. Auto-dismisses after
_DISPLAY_SECS seconds by letting runUntilDate_ return naturally so the
one-shot _check-reminders process can exit without extra cleanup.
"""

from pathlib import Path

_DISPLAY_SECS = 6.0
_POPUP_W = 320
_POPUP_H = 100
_SPRITE_SIZE = 60
_MARGIN = 12
_CORNER_RADIUS = 14.0
# Style mask: 128 = NSWindowStyleMaskNonactivatingPanel (borderless panel
# that never steals key-window status from the current foreground app).
_PANEL_STYLE = 128


def show_popup(title: str, message: str, sprite_path: Path | None) -> bool:
    """Show a borderless floating panel near the top-right of the main screen.

    Blocks for _DISPLAY_SECS while the NSRunLoop renders the panel, then
    closes it and returns True. Returns False on any failure (no display,
    missing PyObjC, anything) so the caller can fall back to osascript.
    """
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
        from Foundation import NSDate, NSMakeRect, NSMakeSize, NSRunLoop

        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        screen = NSScreen.mainScreen()
        if screen is None:
            return False

        vf = screen.visibleFrame()
        x = vf.origin.x + vf.size.width - _POPUP_W - 20
        y = vf.origin.y + vf.size.height - _POPUP_H - 20

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, _POPUP_W, _POPUP_H),
            _PANEL_STYLE,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setHasShadow_(True)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setIgnoresMouseEvents_(True)

        # NSBox gives us a rounded-rect fill using NSColor directly —
        # avoids the CGColor bridging quirks in PyObjC 12.
        box = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, _POPUP_W, _POPUP_H))
        box.setBoxType_(4)  # NSBoxCustom
        box.setFillColor_(
            NSColor.colorWithSRGBRed_green_blue_alpha_(1.0, 0.97, 0.93, 0.95)
        )
        box.setBorderWidth_(0)
        box.setCornerRadius_(_CORNER_RADIUS)
        box.setContentViewMargins_(NSMakeSize(0, 0))
        cv = box.contentView()

        # Sprite (alert pose — the "something needs attention" frame)
        if sprite_path is not None:
            ns_img = NSImage.alloc().initWithContentsOfFile_(str(sprite_path))
            if ns_img is not None:
                sprite_y = (_POPUP_H - _SPRITE_SIZE) // 2
                iv = NSImageView.alloc().initWithFrame_(
                    NSMakeRect(_MARGIN, sprite_y, _SPRITE_SIZE, _SPRITE_SIZE)
                )
                iv.setImage_(ns_img)
                iv.setImageScaling_(NSImageScaleProportionallyUpOrDown)
                cv.addSubview_(iv)

        text_x = _MARGIN + _SPRITE_SIZE + _MARGIN  # 84
        text_w = _POPUP_W - text_x - _MARGIN       # 224

        title_h = 17
        title_y = _POPUP_H - _MARGIN - title_h     # 71

        tf_title = NSTextField.alloc().initWithFrame_(
            NSMakeRect(text_x, title_y, text_w, title_h)
        )
        tf_title.setStringValue_(title)
        tf_title.setEditable_(False)
        tf_title.setSelectable_(False)
        tf_title.setBezeled_(False)
        tf_title.setDrawsBackground_(False)
        tf_title.setFont_(NSFont.boldSystemFontOfSize_(13.0))
        tf_title.setTextColor_(NSColor.labelColor())
        cv.addSubview_(tf_title)

        msg_h = 38
        msg_y = title_y - 5 - msg_h               # 26

        tf_msg = NSTextField.alloc().initWithFrame_(
            NSMakeRect(text_x, msg_y, text_w, msg_h)
        )
        tf_msg.setStringValue_(message)
        tf_msg.setEditable_(False)
        tf_msg.setSelectable_(False)
        tf_msg.setBezeled_(False)
        tf_msg.setDrawsBackground_(False)
        tf_msg.setFont_(NSFont.systemFontOfSize_(12.0))
        tf_msg.setTextColor_(NSColor.secondaryLabelColor())
        tf_msg.cell().setWraps_(True)
        cv.addSubview_(tf_msg)

        panel.setContentView_(box)
        panel.orderFrontRegardless()

        # Block the run loop for _DISPLAY_SECS then let it return naturally.
        # The process exits normally after show_popup() returns.
        NSRunLoop.mainRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(_DISPLAY_SECS)
        )
        panel.close()
        return True

    except Exception:
        return False
