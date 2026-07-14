"""Wake-time AI check-in: berry greets you and you can type back.

Flow: Mac wakes -> BerryMenuBar._on_wake -> show_checkin(). berry
greets you in a small floating bubble with a real text field -- the
first focusable window berry has ever had. Focus is deliberately
brief: the input panel takes key status only while it's on screen, and
gives it back the moment you submit (Enter), dismiss (Esc), or ignore
it long enough for the timeout. The reply is then shown in a separate
passive bubble that -- like every other berry panel -- ignores the
mouse and never takes focus.

Same defensive contract as popup.py/companion.py: any AppKit failure
is a silent no-op. The LLM call runs on a background thread so the
menu bar app's run loop never blocks, with the result hopped back to
the main thread via performSelectorOnMainThread.
"""

from __future__ import annotations

import threading
from pathlib import Path

from berry.ai import FALLBACK_REPLY

CHECKIN_COOLDOWN_SECS = 600.0  # at most one check-in per 10 minutes
INPUT_TIMEOUT_SECS = 30.0      # an unanswered greeting goes away on its own
REPLY_DISPLAY_SECS = 8.0

_PANEL_W = 360
_INPUT_H = 92
_REPLY_H = 100
_SPRITE_SIZE = 60
_MARGIN = 12
_CORNER_RADIUS = 14.0
# Style mask: 128 = NSWindowStyleMaskNonactivatingPanel (see popup.py) --
# the panel can become key without activating the whole app, so the
# frontmost app stays frontmost while you type to berry.
_PANEL_STYLE = 128
# Vertical clearance so the bubble sits just below the companion sprite.
_TOP_CLEARANCE = 130

# PyObjC classes can only be registered once per process; cache them so
# repeated wake events don't try to redefine them.
_objc_classes: dict[str, type] = {}
# Keep panels/controllers referenced while on screen -- NSControl holds
# its target weakly, so without this the controller (and the callbacks
# hanging off it) would be garbage-collected mid-conversation.
_active_sessions: list[dict] = []


def due_for_checkin(
    last_checkin: float, now: float, cooldown: float = CHECKIN_COOLDOWN_SECS
) -> bool:
    """True when enough time has passed since the last check-in fired."""
    return (now - last_checkin) >= cooldown


def greeting_text(name: str) -> str:
    return f"{name} stretches awake — hey, how are you doing?"


def _panel_class():
    cls = _objc_classes.get("panel")
    if cls is None:
        from AppKit import NSPanel

        class _BerryKeyPanel(NSPanel):
            # Borderless windows refuse key status by default; the
            # input panel genuinely needs it while the field is up.
            def canBecomeKeyWindow(self):
                return True

        cls = _objc_classes["panel"] = _BerryKeyPanel
    return cls


def _controller_class():
    cls = _objc_classes.get("controller")
    if cls is None:
        from Foundation import NSObject

        class _BerryCheckinController(NSObject):
            """Objective-C bridge: Enter/Esc in the field, timed closes,
            and the main-thread hop for the background AI reply. The
            actual logic lives in python callbacks set as _berry_*
            attributes by show_checkin()."""

            def submit_(self, _sender):
                cb = getattr(self, "_berry_on_submit", None)
                if cb is not None:
                    cb()

            def cancelInput_(self, _arg):
                cb = getattr(self, "_berry_on_cancel", None)
                if cb is not None:
                    cb()

            def showReply_(self, text):
                cb = getattr(self, "_berry_on_reply", None)
                if cb is not None:
                    cb(str(text))

            def closeReply_(self, _arg):
                cb = getattr(self, "_berry_on_reply_done", None)
                if cb is not None:
                    cb()

            def control_textView_doCommandBySelector_(self, _control, _tv, selector):
                if str(selector) == "cancelOperation:":
                    cb = getattr(self, "_berry_on_cancel", None)
                    if cb is not None:
                        cb()
                        return True
                return False

        cls = _objc_classes["controller"] = _BerryCheckinController
    return cls


def _make_bubble(height: float, interactive: bool):
    """Rounded floating bubble, top-center below the companion.

    Returns (panel, content view). Raises on any AppKit failure --
    callers wrap in try/except per the module contract.
    """
    from AppKit import (
        NSBackingStoreBuffered,
        NSBox,
        NSColor,
        NSFloatingWindowLevel,
        NSPanel,
        NSScreen,
    )
    from Foundation import NSMakeRect, NSMakeSize

    screen = NSScreen.mainScreen()
    if screen is None:
        raise RuntimeError("no display")

    vf = screen.visibleFrame()
    x = vf.origin.x + (vf.size.width - _PANEL_W) / 2
    y = vf.origin.y + vf.size.height - _TOP_CLEARANCE - height

    panel_cls = _panel_class() if interactive else NSPanel
    panel = panel_cls.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, _PANEL_W, height),
        _PANEL_STYLE,
        NSBackingStoreBuffered,
        False,
    )
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(not interactive)
    # PyObjC owns the panel's lifetime; releasedWhenClosed would
    # double-free it on close().
    panel.setReleasedWhenClosed_(False)

    box = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, _PANEL_W, height))
    box.setBoxType_(4)  # NSBoxCustom, as in popup.py
    box.setFillColor_(
        NSColor.colorWithSRGBRed_green_blue_alpha_(1.0, 0.97, 0.93, 0.95)
    )
    box.setBorderWidth_(0)
    box.setCornerRadius_(_CORNER_RADIUS)
    box.setContentViewMargins_(NSMakeSize(0, 0))
    panel.setContentView_(box)
    return panel, box.contentView()


def _make_label(frame, text: str, font, color):
    from AppKit import NSTextField

    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setFont_(font)
    label.setTextColor_(color)
    return label


def _show_reply_panel(name: str, sprite_path: Path | None):
    """Passive '<name> is thinking...' bubble; returns (panel, message label)."""
    from AppKit import (
        NSColor,
        NSFont,
        NSImage,
        NSImageScaleProportionallyUpOrDown,
        NSImageView,
    )
    from Foundation import NSMakeRect

    panel, cv = _make_bubble(_REPLY_H, interactive=False)

    text_x = _MARGIN
    if sprite_path is not None:
        ns_img = NSImage.alloc().initWithContentsOfFile_(str(sprite_path))
        if ns_img is not None:
            sprite_y = (_REPLY_H - _SPRITE_SIZE) // 2
            iv = NSImageView.alloc().initWithFrame_(
                NSMakeRect(_MARGIN, sprite_y, _SPRITE_SIZE, _SPRITE_SIZE)
            )
            iv.setImage_(ns_img)
            iv.setImageScaling_(NSImageScaleProportionallyUpOrDown)
            cv.addSubview_(iv)
            text_x = _MARGIN + _SPRITE_SIZE + _MARGIN

    message = _make_label(
        NSMakeRect(text_x, _MARGIN, _PANEL_W - text_x - _MARGIN, _REPLY_H - 2 * _MARGIN),
        f"{name} is thinking...",
        NSFont.systemFontOfSize_(12.0),
        NSColor.labelColor(),
    )
    message.cell().setWraps_(True)
    cv.addSubview_(message)

    panel.orderFrontRegardless()
    return panel, message


def show_checkin(backend, context: dict, sprite_path: Path | None = None) -> bool:
    """Show the greeting + typed-reply bubble. Returns True if it went up.

    Enter submits, Esc dismisses, and an unanswered greeting times out
    after INPUT_TIMEOUT_SECS. Returns False on any AppKit failure (same
    contract as popup.show_popup) so the caller just skips the check-in.
    """
    try:
        from AppKit import NSColor, NSFont, NSTextField
        from Foundation import NSMakeRect

        name = str(context.get("name", "berry"))
        panel, cv = _make_bubble(_INPUT_H, interactive=True)

        label_h = 17
        label_y = _INPUT_H - _MARGIN - label_h
        cv.addSubview_(
            _make_label(
                NSMakeRect(_MARGIN, label_y, _PANEL_W - 2 * _MARGIN, label_h),
                greeting_text(name),
                NSFont.boldSystemFontOfSize_(13.0),
                NSColor.labelColor(),
            )
        )

        field_h = 24
        field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(_MARGIN, label_y - 10 - field_h, _PANEL_W - 2 * _MARGIN, field_h)
        )
        field.setFont_(NSFont.systemFontOfSize_(12.0))
        field.setPlaceholderString_("type back — Enter sends, Esc dismisses")
        cv.addSubview_(field)

        controller = _controller_class().alloc().init()
        field.setTarget_(controller)
        field.setAction_("submit:")
        field.setDelegate_(controller)

        session = {"controller": controller, "input": panel, "reply": None}
        _active_sessions.append(session)

        def end_session():
            try:
                _active_sessions.remove(session)
            except ValueError:
                pass

        input_closed = [False]

        def close_input():
            # Closing the key panel is what hands keyboard focus back
            # to whatever app the user was in before the greeting.
            if input_closed[0]:
                return
            input_closed[0] = True
            try:
                type(controller).cancelPreviousPerformRequestsWithTarget_(controller)
                panel.close()
            except Exception:
                pass

        def on_cancel():
            close_input()
            end_session()

        def on_submit():
            try:
                if input_closed[0]:
                    return
                text = str(field.stringValue()).strip()
                close_input()
                if not text:
                    end_session()
                    return
                try:
                    reply_panel, reply_label = _show_reply_panel(name, sprite_path)
                except Exception:
                    end_session()
                    return
                session["reply"] = reply_panel

                def on_reply(reply_text: str):
                    try:
                        reply_label.setStringValue_(reply_text)
                        controller.performSelector_withObject_afterDelay_(
                            "closeReply:", None, REPLY_DISPLAY_SECS
                        )
                    except Exception:
                        on_reply_done()

                def on_reply_done():
                    try:
                        reply_panel.close()
                    except Exception:
                        pass
                    end_session()

                controller._berry_on_reply = on_reply
                controller._berry_on_reply_done = on_reply_done

                def work():
                    try:
                        reply = backend.reply(text, dict(context))
                    except Exception:
                        reply = FALLBACK_REPLY
                    try:
                        controller.performSelectorOnMainThread_withObject_waitUntilDone_(
                            "showReply:", reply, False
                        )
                    except Exception:
                        pass

                threading.Thread(target=work, daemon=True).start()
            except Exception:
                end_session()

        controller._berry_on_submit = on_submit
        controller._berry_on_cancel = on_cancel

        panel.makeKeyAndOrderFront_(None)
        panel.makeFirstResponder_(field)
        controller.performSelector_withObject_afterDelay_(
            "cancelInput:", None, INPUT_TIMEOUT_SECS
        )
        return True
    except Exception:
        return False
