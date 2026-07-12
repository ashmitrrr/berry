"""Recolor and slice Cat-1 sprite sheets into per-frame PNGs.

Hue-shifts the original art to raspberry/magenta while keeping:
  - Near-black outline pixels untouched (value < 0.18)
  - Shading/value intact (only hue is remapped)
  - Alpha channel preserved

Writes frames to src/berry/assets/cat/<mood>/frame_NN.png
"""

import colorsys
from pathlib import Path

from PIL import Image

RAW = Path(__file__).parent.parent / "raw-assets" / "Pet Cats Pack" / "Cat-1"
OUT = Path(__file__).parent.parent / "src" / "berry" / "assets" / "cat"

# Target hue in degrees — raspberry/magenta sits around 330°
TARGET_HUE = 330 / 360.0
# Pixels with HSV value below this are treated as outline/shadow and kept black
OUTLINE_VALUE_THRESHOLD = 0.18
# Pixels with saturation below this are treated as white/grey and skipped
MIN_SATURATION = 0.08

SHEETS = [
    ("Cat-1-Idle.png",        10, "idle"),
    ("Cat-1-Stretching.png",  13, "happy"),
    ("Cat-1-Meow.png",         4, "hungry"),
    ("Cat-1-Sleeping1.png",    1, "sleeping"),
    ("Cat-1-Sleeping2.png",    1, "sleeping"),   # appended as frame 2
    ("Cat-1-Itch.png",         2, "alert"),
    ("Cat-1-Run.png",          8, "running"),
]

FRAME_W = 50
FRAME_H = 50


def recolor_pixel(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Hue-shift one RGB pixel toward raspberry/magenta."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)

    if v < OUTLINE_VALUE_THRESHOLD:
        return r, g, b

    if s < MIN_SATURATION:
        return r, g, b

    nr, ng, nb = colorsys.hsv_to_rgb(TARGET_HUE, s, v)
    return int(nr * 255), int(ng * 255), int(nb * 255)


def recolor_image(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            nr, ng, nb = recolor_pixel(r, g, b)
            pixels[x, y] = (nr, ng, nb, a)
    return img


def slice_sheet(img: Image.Image, n_frames: int) -> list[Image.Image]:
    frames = []
    for i in range(n_frames):
        box = (i * FRAME_W, 0, (i + 1) * FRAME_W, FRAME_H)
        frames.append(img.crop(box))
    return frames


def main() -> None:
    # Track per-mood frame counters so sleeping sheets append sequentially
    mood_counters: dict[str, int] = {}

    for filename, n_frames, mood_name in SHEETS:
        src = RAW / filename
        if not src.exists():
            print(f"  SKIP (not found): {src}")
            continue

        mood_dir = OUT / mood_name
        mood_dir.mkdir(parents=True, exist_ok=True)

        img = Image.open(src)
        recolored = recolor_image(img)
        frames = slice_sheet(recolored, n_frames)

        start = mood_counters.get(mood_name, 0)
        for i, frame in enumerate(frames):
            idx = start + i + 1
            out_path = mood_dir / f"frame_{idx:02d}.png"
            frame.save(out_path)
            print(f"  wrote {out_path.relative_to(OUT.parent.parent)}")

        mood_counters[mood_name] = start + n_frames

    print("\nDone.")


if __name__ == "__main__":
    main()
