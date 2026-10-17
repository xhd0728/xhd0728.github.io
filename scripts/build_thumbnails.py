"""Build responsive paper/project thumbnails. Optional dependency: Pillow.

Full-size source images remain unchanged for the image preview and direct links.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for category in ("paper", "projects"):
    output = ROOT / "images/thumbs" / category
    output.mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "images" / category).glob("*.webp")):
        with Image.open(source) as image:
            for width in (400, 640, 800):
                thumbnail = image.convert("RGB")
                thumbnail.thumbnail((width, 10000), Image.Resampling.LANCZOS)
                thumbnail.save(output / f"{source.stem}-{width}.webp", "WEBP", quality=82, method=6)
print("Built 400, 640 and 800 px WebP thumbnails; original images preserved.")
