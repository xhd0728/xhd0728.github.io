"""Build local Shields.io flat badges from _data/resource_badges.json.

Network access is only needed when authoring badges, not for normal site builds.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def escape_part(text):
    # Shields path syntax uses doubled underscores and dashes for literal values.
    return quote(text.replace("_", "__").replace("-", "--"), safe="")


def build_badge(item):
    key, badge = item
    label, message = badge["label"], badge["message"]
    url = "https://img.shields.io/badge/" + "-".join([
        escape_part(label), escape_part(message), badge["color"],
    ]) + "?" + urlencode({"style": "flat", "logo": badge["logo"], "logoColor": "white"})
    request = Request(url, headers={"User-Agent": "HaidongXin-PersonalSite"})
    with urlopen(request, timeout=30) as response:
        data = response.read()
    svg = ElementTree.fromstring(data)
    assert svg.tag == "{http://www.w3.org/2000/svg}svg"
    assert svg.attrib.get("aria-label") == f"{label}: {message}", f"Incomplete badge text: {key}"
    width, height = int(svg.attrib["width"]), int(svg.attrib["height"])
    assert width > 0 and height == 20
    output = ROOT / "images/resource-badges" / f"{key}.svg"
    output.write_bytes(data)
    print(f"{label}: {message} ({width} × {height})")
    return key, {
        **badge,
        "image": f"/images/resource-badges/{key}.svg",
        "width": width,
        "height": height,
        "version": hashlib.sha256(data).hexdigest()[:12],
    }


def main():
    manifest = ROOT / "_data/resource_badges.json"
    badges = json.loads(manifest.read_text())
    (ROOT / "images/resource-badges").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        badges = dict(executor.map(build_badge, badges.items()))
    manifest.write_text(json.dumps(badges, indent=2) + "\n")


if __name__ == "__main__":
    main()
