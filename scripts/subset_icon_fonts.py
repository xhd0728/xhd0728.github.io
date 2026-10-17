"""Rebuild checked-in WOFF2 icon subsets after adding icons to the templates.

Optional authoring dependency: pip install 'fonttools[woff]'.
Normal Jekyll builds use the generated fonts and do not require Python packages.
Original font files and their embedded licensing information are preserved.
"""

import re
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
source = "\n".join(
    path.read_text()
    for directory in ("_includes", "_pages")
    for path in (ROOT / directory).rglob("*")
    if path.is_file()
)
variables = (ROOT / "_sass/vendor/font-awesome/_variables.scss").read_text()
fa_map = dict(re.findall(r"\$fa-var-([\w-]+):\s*\\([0-9a-f]+);", variables))
fa_codes = {int(fa_map[name], 16) for name in re.findall(r"\bfa-([\w-]+)", source) if name in fa_map}
ai_css = (ROOT / "assets/css/academicons.css").read_text()
ai_map = dict(re.findall(r'\.ai-([\w-]+):before\s*\{\s*content:\s*"\\([0-9a-f]+)";', ai_css))
ai_codes = {int(ai_map[name], 16) for name in re.findall(r"\bai-([\w-]+)", source) if name in ai_map}

for filename, output, codes in [
    ("fa-solid-900.woff2", "site-fa-solid.woff2", fa_codes),
    ("fa-brands-400.woff2", "site-fa-brands.woff2", fa_codes),
    ("academicons.ttf", "site-academicons.woff2", ai_codes),
]:
    font = TTFont(ROOT / "assets/fonts" / filename)
    options = subset.Options()
    options.flavor = "woff2"
    options.name_IDs = ["*"]
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codes)
    subsetter.subset(font)
    # Give modified fonts distinct internal names; retain copyright/license records.
    for record in font["name"].names:
        if record.nameID in (1, 3, 4, 6, 16):
            value = "SiteIcons" + output.removesuffix(".woff2").replace("-", "")
            record.string = value.encode(record.getEncoding())
    font.flavor = "woff2"
    path = ROOT / "assets/fonts" / output
    font.save(path)
    print(f"{path.name}: {path.stat().st_size:,} bytes")
