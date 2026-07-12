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


MENUBAR_PAD = 2   # transparent-free margin kept around the cropped content


def _union_bbox(frames: list[Image.Image]) -> tuple[int, int, int, int]:
    """Return the union of all non-transparent bounding boxes in frames."""
    bboxes = [f.getbbox() for f in frames]
    bboxes = [b for b in bboxes if b is not None]
    if not bboxes:
        return (0, 0, FRAME_W, FRAME_H)
    return (
        min(b[0] for b in bboxes),
        min(b[1] for b in bboxes),
        max(b[2] for b in bboxes),
        max(b[3] for b in bboxes),
    )


def main() -> None:
    # Phase 1 — accumulate all decoded frames per mood so we can compute a
    # shared union bounding box.  A per-mood box (not per-frame) keeps the
    # cat's apparent size consistent across animation frames, preventing jitter.
    mood_all_frames: dict[str, list[Image.Image]] = {}
    for filename, n_frames, mood_name in SHEETS:
        src = RAW / filename
        if not src.exists():
            continue
        frames = slice_sheet(recolor_image(Image.open(src)), n_frames)
        mood_all_frames.setdefault(mood_name, []).extend(frames)

    # Padded union crop box per mood.
    mood_crop: dict[str, tuple[int, int, int, int]] = {}
    for mood_name, frames in mood_all_frames.items():
        ux, uy, uw, uh = _union_bbox(frames)
        mood_crop[mood_name] = (
            max(0,      ux - MENUBAR_PAD),
            max(0,      uy - MENUBAR_PAD),
            min(FRAME_W, uw + MENUBAR_PAD),
            min(FRAME_H, uh + MENUBAR_PAD),
        )

    # Phase 2 — write frames.  Full-size frame_NN.png is unchanged (used by
    # status / feed / watch / terminal renderer).  Menubar variants crop to the
    # shared per-mood bbox before nearest-neighbor scaling so the cat fills the
    # icon canvas instead of being a tiny blob in mostly-empty space.
    mood_counters: dict[str, int] = {}
    for filename, n_frames, mood_name in SHEETS:
        src = RAW / filename
        if not src.exists():
            print(f"  SKIP (not found): {src}")
            continue

        mood_dir = OUT / mood_name
        mood_dir.mkdir(parents=True, exist_ok=True)

        frames = slice_sheet(recolor_image(Image.open(src)), n_frames)
        crop_box = mood_crop[mood_name]
        crop_w = crop_box[2] - crop_box[0]
        crop_h = crop_box[3] - crop_box[1]

        start = mood_counters.get(mood_name, 0)
        if start == 0:
            fill = round(crop_w * crop_h / (FRAME_W * FRAME_H) * 100)
            print(f"  [{mood_name}] menubar crop {crop_box}  {crop_w}×{crop_h}px  ({fill}% of canvas)")

        for i, frame in enumerate(frames):
            idx = start + i + 1
            out_path = mood_dir / f"frame_{idx:02d}.png"
            frame.save(out_path)
            print(f"  wrote {out_path.relative_to(OUT.parent.parent)}")

            cropped = frame.crop(crop_box)
            for size, suffix in [(20, "_menubar"), (40, "_menubar@2x")]:
                cropped.resize((size, size), Image.NEAREST).save(
                    mood_dir / f"frame_{idx:02d}{suffix}.png"
                )

        mood_counters[mood_name] = start + n_frames

    print("\nDone.")


if __name__ == "__main__":
    main()
