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
                # Composite alpha onto the page background before discarding it.
                # A direct RGB conversion exposes hidden black pixels in PDFs' diagrams.
                thumbnail = Image.new("RGB", image.size, "white")
                if "A" in image.getbands() or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    thumbnail.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    thumbnail.paste(image.convert("RGB"))
                thumbnail.thumbnail((width, 10000), Image.Resampling.LANCZOS)
                thumbnail.save(output / f"{source.stem}-{width}.webp", "WEBP", quality=82, method=6)
print("Built 400, 640 and 800 px WebP thumbnails; original images preserved.")
