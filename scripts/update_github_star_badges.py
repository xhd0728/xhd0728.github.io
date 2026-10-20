"""Refresh local GitHub star badges; retain saved badges if Shields is unavailable."""
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = {
    "staffdeck": "OpenBMB/StaffDeck",
    "pilotdeck": "OpenBMB/PilotDeck",
    "ultrarag": "OpenBMB/UltraRAG",
    "heu-icicles": "HEUOpenResource/heu-icicles",
    "t2mem": "OpenBMB/T2Mem",
    "metamem": "OpenBMB/MetaMem",
    "lisrec": "NEUIR/LISRec",
    "taste-plus": "NEUIR/TASTE-plus",
    "mmad": "Daria8976/MMAD",
    "memshot": "NEUIR/MemShot",
    "cagmamba": "User2024-xj/CAGMamba",
    "pager": "OpenBMB/PAGER",
}


def read_badge(data):
    svg = ElementTree.fromstring(data)
    assert svg.tag == "{http://www.w3.org/2000/svg}svg", "Expected an SVG badge"
    text = [
        node.text.strip() for node in svg.iter("{http://www.w3.org/2000/svg}text")
        if node.text and node.attrib.get("aria-hidden") != "true"
    ]
    assert len(text) >= 2 and text[0] == "Code Stars", "Missing badge label"
    assert re.fullmatch(r"\d+(?:[.,]\d+)*(?:[kKmM])?", text[-1]), "Missing star count"
    label = "Code Stars: " + text[-1]
    width, height = int(svg.attrib["width"]), int(svg.attrib["height"])
    assert width > 0 and height == 20, "Unexpected badge dimensions"
    return label, width, height


def update_badge(item):
    slug, repo = item
    output = ROOT / "images/github-stars" / f"{slug}.svg"
    url = f"https://img.shields.io/github/stars/{repo}?style=social&label=Code+Stars"
    request = Request(url, headers={"User-Agent": "HaidongXin-PersonalSite"})
    try:
        with urlopen(request, timeout=25) as response:
            data = response.read()
        read_badge(data)
        output.write_bytes(data)
    except (OSError, ValueError, AssertionError, ElementTree.ParseError) as error:
        if not output.exists():
            raise RuntimeError(f"Cannot initialize {repo} badge: {error}") from error
        print(f"Warning: keeping saved {repo} badge: {error}", file=sys.stderr)
        data = output.read_bytes()
    label, width, height = read_badge(data)
    print(f"{repo}: {label}")
    return slug, {
        "repo": repo,
        "image": f"/images/github-stars/{slug}.svg",
        "label": label,
        "width": width,
        "height": height,
        "version": hashlib.sha256(data).hexdigest()[:12],
    }


def main():
    (ROOT / "images/github-stars").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        badges = dict(executor.map(update_badge, REPOSITORIES.items()))
    (ROOT / "_data/github_star_badges.json").write_text(json.dumps(badges, indent=2) + "\n")


if __name__ == "__main__":
    main()
