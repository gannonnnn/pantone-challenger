#!/usr/bin/env python3
"""Normalize a manually approved raster brand mark without stretching or cover-cropping."""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image


def trim_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("The image is fully transparent.")
    return rgba.crop(bbox)


def normalize(source: Path, destination: Path, width: int = 480, height: int = 240) -> None:
    with Image.open(source) as raw:
        raw.load()
        mark = trim_alpha(raw)
    if mark.width < 32 or mark.height < 16:
        raise ValueError("Source mark is too small for safe public rendering.")
    inner_w = int(width * 0.68)
    inner_h = int(height * 0.68)
    scale = min(inner_w / mark.width, inner_h / mark.height, 2.0)
    target = (max(1, round(mark.width * scale)), max(1, round(mark.height * scale)))
    mark = mark.resize(target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    canvas.alpha_composite(mark, ((width - mark.width) // 2, (height - mark.height) // 2))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=240)
    args = parser.parse_args()
    normalize(args.source, args.destination, args.width, args.height)
    print(args.destination)


if __name__ == "__main__":
    main()
