from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw


def make_checkerboard(width: int, height: int, cell: int = 8) -> Image.Image:
    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)
    toggle = 0
    for y in range(0, height, cell):
        toggle = 1 - toggle
        for x in range(0, width, cell):
            color = 0 if (toggle == 0) else 180
            draw.rectangle((x, y, min(x + cell - 1, width - 1), min(y + cell - 1, height - 1)), fill=color)
            toggle = 1 - toggle
    # Add a few diagonal lines for additional edges
    for i in range(0, min(width, height), cell * 10):
        draw.line((0, i, i, 0), fill=50, width=2)
        draw.line((width - 1, i, width - 1 - i, 0), fill=220, width=2)
    return img.convert("RGB")


def main(argv):
    if len(argv) < 3:
        print("usage: python3 scripts/generate_synthetic_images.py <out_dir> <count> [width height]", file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    count = int(argv[2])
    width = int(argv[3]) if len(argv) >= 4 else 1200
    height = int(argv[4]) if len(argv) >= 5 else 800
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        img = make_checkerboard(width, height, cell=8)
        img.save(out_dir / f"img_{i:04d}.jpg", format="JPEG", quality=92, optimize=True)
    print(f"✅ Generated {count} images at {width}x{height} in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


