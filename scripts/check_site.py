"""Check the generated site for broken local resources and bilingual drift.

Run after a production build: python3 scripts/check_site.py [_site]
Uses only the Python standard library, so the same check runs in CI.
"""

import json
import hashlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from site_text import chinese_characters


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.references = []
        self.metadata = {}
        self.duplicates = []
        self.jsonld = []
        self.in_jsonld = False
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            if attrs["id"] in self.ids:
                self.duplicates.append(attrs["id"])
            self.ids.add(attrs["id"])
        for attribute in ("href", "src"):
            if attrs.get(attribute):
                self.references.append(attrs[attribute])
        for candidate in attrs.get("srcset", "").split(","):
            if candidate.strip():
                self.references.append(candidate.strip().split()[0])
        if tag == "html":
            self.metadata["lang"] = attrs.get("lang")
        if tag == "meta":
            self.metadata[attrs.get("property", attrs.get("name"))] = attrs.get("content")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.metadata["canonical"] = attrs.get("href")
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_jsonld = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_jsonld = False

    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld.append(json.loads(data))


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    assert (root / "index.html").is_file(), "Build the site first"
    pages = {path: Page(path) for path in root.rglob("*.html")}
    errors = []
    checked = 0

    def check_reference(reference, origin):
        nonlocal checked
        url = urlsplit(reference)
        if url.scheme and url.scheme not in ("http", "https"):
            return
        if url.netloc and url.hostname != "xinhaidong.top":
            return
        # The HTML <base> is the site root. CSS URLs resolve beside the CSS.
        parent = origin.parent if origin.suffix == ".css" else root
        target = root / unquote(url.path).lstrip("/") if url.path.startswith("/") else parent / unquote(url.path)
        target = target.resolve()
        if target.is_dir():
            target /= "index.html"
        checked += 1
        if not target.is_file():
            errors.append(f"{origin.relative_to(root)}: missing {reference}")
        elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
            errors.append(f"{origin.relative_to(root)}: missing anchor {reference}")

    for path, page in pages.items():
        errors.extend(f"{path.relative_to(root)}: duplicate id {value}" for value in page.duplicates)
        for reference in page.references:
            check_reference(reference, path)
    for path in root.rglob("*.css"):
        for reference in re.findall(r"url\(['\"]?([^)'\"]+)", path.read_text()):
            check_reference(reference, path)

    for route, lang in [("index.html", "en"), ("zh_cn/index.html", "zh-CN")]:
        page = pages[root / route]
        expected_url = "https://xinhaidong.top/" + ("zh_cn/" if lang == "zh-CN" else "")
        assert page.metadata["canonical"] == expected_url
        assert page.metadata["lang"] == lang
        check_reference(page.metadata["og:image"], root / route)
        assert page.metadata["og:image:type"] == "image/jpeg"
        assert page.jsonld[0]["@type"] == "ProfilePage"
        assert len(re.findall(r"<h1[ >]", (root / route).read_text())) == 1, "Use a single primary heading"
        text = (root / route).read_text()
        assert text.count("<h3 id=\"test-time-memory-construction\">") == 1, "New paper must appear once"
        assert "https://arxiv.org/abs/2610.13348" in text
        assert "https://github.com/OpenBMB/T2Mem" in text
        assert re.search(r"\d{4}-\d{2}-\d{2}", text)
        assert not re.search(r"\$\^", text), "Author markers should work without MathJax"
        assert "img.shields.io/" not in text, "Resource badges should not depend on an external API"

    en = (root / "index.html").read_text()
    zh = (root / "zh_cn/index.html").read_text()
    for expression in [r"src=['\"](/images/(?:paper|projects)/[^'\"]+)", r"href=\"(https://arxiv.org/abs/[^\"]+)\""]:
        assert re.findall(expression, en) == re.findall(expression, zh), "Bilingual publication/project mismatch"

    manifest = json.loads((root / "images/site.webmanifest").read_text())
    for icon in manifest["icons"]:
        check_reference(icon["src"], root / "index.html")
        assert icon["sizes"] in ("192x192", "512x512")
    for filename in ("sitemap.xml", "feed.xml"):
        ElementTree.parse(root / filename)
    assert not (root / "scripts").exists(), "Do not publish validation source files"
    source_root = Path(__file__).resolve().parents[1]
    coverage = json.loads((root / "assets/fonts/site-zh-coverage.json").read_text())
    assert chinese_characters(source_root) <= set(coverage["characters"]), "Rebuild the Chinese fallback after adding Chinese text"
    font_data = (root / "assets/fonts" / coverage["file"]).read_bytes()
    assert font_data.startswith(b"wOF2") and hashlib.sha256(font_data).hexdigest() == coverage["sha256"], "Chinese font and coverage manifest must match"
    if errors:
        raise AssertionError("\n".join(errors))
    print(f"PASS: {len(pages)} HTML pages, {checked} local references, bilingual content, SEO, manifest, and XML")


if __name__ == "__main__":
    main()
