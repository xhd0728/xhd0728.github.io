"""Build the Chinese fallback from an OFL-licensed Noto Sans SC source TTF.

Usage: python3 scripts/subset_chinese_font.py /path/to/NotoSansSC.ttf
Optional authoring dependency: pip install 'fonttools[woff]'.
"""
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from site_text import chinese_characters

ROOT = Path(__file__).resolve().parents[1]
characters = chinese_characters(ROOT)
font = TTFont(sys.argv[1])
assert {ord(c) for c in characters} <= font.getBestCmap().keys(), "Source font lacks required characters"
options = subset.Options()
options.name_IDs = ["*"]
subsetter = subset.Subsetter(options=options)
subsetter.populate(unicodes={ord(c) for c in characters})
subsetter.subset(font)
if "fvar" in font:
    font = instantiateVariableFont(font, {"wght": 400}, inplace=True)
for record in font["name"].names:
    if record.nameID in (1, 3, 4, 6, 16):
        record.string = "SiteChineseFallback".encode(record.getEncoding())
font.flavor = "woff2"
font.recalcTimestamp = False
font["head"].modified = 2082844800
output = io.BytesIO()
font.save(output)
data = output.getvalue()
digest = hashlib.sha256(data).hexdigest()
filename = f"site-zh-{digest[:12]}.woff2"
(ROOT / "assets/fonts" / filename).write_bytes(data)
metadata = {
    "file": filename,
    "sha256": digest,
    "characters": "".join(sorted(characters)),
    "source": "https://github.com/google/fonts/tree/main/ofl/notosanssc",
    "license": "NotoSansSC-OFL.txt",
}
(ROOT / "assets/fonts/site-zh-coverage.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
styles = ROOT / "_sass/_fonts.scss"
css = styles.read_text()
css = re.sub(r'url\("\.\./fonts/(?:apple/apple-sans-zh-hans|site-zh-[a-f0-9]+)\.woff2"\)', f'url("../fonts/{filename}")', css)
css = css.replace('Apple Site Sans SC', 'Site Sans SC').replace('Simplified Chinese fallback font', 'Chinese fallback from Noto Sans SC (see assets/fonts/NotoSansSC-OFL.txt)')
styles.write_text(css)
variables = ROOT / "_sass/_variables.scss"
variables.write_text(variables.read_text().replace('Apple Site Sans SC', 'Site Sans SC'))
print(f"{filename}: {len(data):,} bytes, {len(characters)} characters, coverage complete")
