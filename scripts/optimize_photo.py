#!/usr/bin/env python3
"""Génère les variantes web légères du portrait, sans modifier l'original."""

from pathlib import Path

from PIL import Image, ImageOps, features
import yaml


ROOT = Path(__file__).resolve().parent.parent
SIZES = (180, 360)


def configured_source() -> Path:
    data = yaml.safe_load((ROOT / "cv.yml").read_text(encoding="utf-8"))
    source = (ROOT / data["person"]["photo"]).resolve()
    if ROOT not in source.parents or not source.is_file():
        raise SystemExit("person.photo doit désigner une image présente dans le projet")
    return source


def main() -> None:
    if not features.check("webp") or not features.check("avif"):
        raise SystemExit("Pillow doit prendre en charge WebP et AVIF")

    source_path = configured_source()
    if source_path.suffix.lower() == ".svg":
        print("Portrait SVG : aucune variante raster à générer")
        return

    output_base = source_path.with_suffix("")
    with Image.open(source_path) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        for size in SIZES:
            image = ImageOps.fit(source, (size, size), method=Image.Resampling.LANCZOS)
            outputs = {
                output_base.with_name(f"{output_base.name}-{size}.avif"): {"quality": 55},
                output_base.with_name(f"{output_base.name}-{size}.webp"): {"quality": 78, "method": 6},
                output_base.with_name(f"{output_base.name}-{size}.jpg"): {"quality": 82, "optimize": True, "progressive": True},
            }
            for path, options in outputs.items():
                image.save(path, **options)
                print(f"generated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
