"""PNG sprite -> terminal pixel art renderer.

Uses the "half-block" trick: each terminal character cell can show two
stacked pixels by drawing the upper-half-block character (▀) with a
distinct foreground color (top pixel) and background color (bottom
pixel). This doubles vertical resolution and lets small pixel-art PNGs
render as genuine colored pixel art in any truecolor terminal.
"""

from pathlib import Path

from PIL import Image
from rich.style import Style
from rich.text import Text

UPPER_HALF_BLOCK = "▀"
LOWER_HALF_BLOCK = "▄"


def _rgb(pixel: tuple[int, int, int, int]) -> str:
    r, g, b, _a = pixel
    return f"rgb({r},{g},{b})"


def render_sprite(path: str | Path) -> Text:
    """Render a small PNG sprite as colored half-block terminal art.

    Transparent pixels (alpha == 0) are left as blank terminal
    background so sprites don't need a matching background color.
    """
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    out = Text()
    for y in range(0, height, 2):
        for x in range(width):
            top = pixels[x, y]
            bottom = pixels[x, y + 1] if y + 1 < height else (0, 0, 0, 0)

            top_visible = top[3] > 0
            bottom_visible = bottom[3] > 0

            if not top_visible and not bottom_visible:
                out.append(" ")
            elif top_visible and bottom_visible:
                out.append(
                    UPPER_HALF_BLOCK,
                    style=Style(color=_rgb(top), bgcolor=_rgb(bottom)),
                )
            elif top_visible:
                out.append(UPPER_HALF_BLOCK, style=Style(color=_rgb(top)))
            else:
                out.append(LOWER_HALF_BLOCK, style=Style(color=_rgb(bottom)))
        if y + 2 < height:
            out.append("\n")
    return out
