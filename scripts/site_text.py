"""Characters needed by the Chinese font fallback, including dynamic UI labels."""
import re
from pathlib import Path


def chinese_characters(root: Path) -> set[str]:
    files = [root / "_config.yml", root / "assets/js/main.js"]
    files += list((root / "_pages").rglob("*.md"))
    files += list((root / "_includes").rglob("*.html"))
    files += list((root / "_data").glob("*.yml"))
    return set(re.findall(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", "\n".join(p.read_text() for p in files)))
