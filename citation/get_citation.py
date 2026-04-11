#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

BASE_URL = "https://scholar.google.com/citations"
DIGIT_RE = re.compile(r"\d+")
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
BLOCK_HINTS = (
    "our systems have detected unusual traffic",
    "not a robot",
    "verify you're not a robot",
    "please show you're not a robot",
    "recaptcha",
    "/sorry/",
    "gs_captcha_ccl",
    "g-recaptcha",
)


class ScholarFetchError(RuntimeError):
    """Raised when Google Scholar stats cannot be fetched from the public profile."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Google Scholar citation stats from a public profile page."
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("SCHOLAR_USER_ID"),
        help="Google Scholar profile user id, e.g. 8VCnj3sAAAAJ.",
    )
    parser.add_argument(
        "--hl",
        default=os.environ.get("SCHOLAR_LANGUAGE", "en"),
        help="Google Scholar UI language used in the output profile URL. Defaults to en.",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("SCHOLAR_OUTPUT", "gs_data.json"),
        help="Output JSON path. Defaults to gs_data.json.",
    )
    parser.add_argument(
        "--pagesize",
        type=int,
        default=int(os.environ.get("SCHOLAR_PAGE_SIZE", "100")),
        help="Google Scholar page size. Defaults to 100.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=int(os.environ.get("SCHOLAR_MAX_PAGES", "5")),
        help="Maximum number of profile pages to scan. Defaults to 5.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("SCHOLAR_TIMEOUT", "20")),
        help="Per-request timeout in seconds. Defaults to 20.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("SCHOLAR_RETRIES", "3")),
        help="Number of retries for each profile page. Defaults to 3.",
    )
    args = parser.parse_args()
    if not args.user_id:
        parser.error("--user-id is required unless SCHOLAR_USER_ID is set.")
    if args.pagesize <= 0:
        parser.error("--pagesize must be greater than 0.")
    if args.max_pages <= 0:
        parser.error("--max-pages must be greater than 0.")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0.")
    if args.retries <= 0:
        parser.error("--retries must be greater than 0.")
    return args


def build_profile_url(user_id: str, hl: str) -> str:
    return f"{BASE_URL}?{urlencode({'user': user_id, 'hl': hl})}"


def build_page_url(user_id: str, hl: str, *, cstart: int = 0, pagesize: int = 100) -> str:
    return f"{BASE_URL}?{urlencode({'user': user_id, 'hl': hl, 'cstart': cstart, 'pagesize': pagesize})}"


def extract_first_int(text: str | None) -> int | None:
    if not text:
        return None
    match = DIGIT_RE.search(text.replace(",", ""))
    if not match:
        return None
    return int(match.group(0))


def normalize_publication_id(publication_id: str | None) -> str | None:
    if not publication_id:
        return None
    _, _, suffix = publication_id.partition(":")
    return suffix or publication_id


def build_payload(
    *,
    user_id: str,
    hl: str,
    scholar_name: str | None,
    citedby: int,
    publications: dict[str, dict[str, int | str]],
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "profile_url": build_profile_url(user_id=user_id, hl=hl),
        "scholar_name": scholar_name,
        "citedby": citedby,
        "publications": publications,
        "source_backend": "direct-html",
    }


def is_blocked_response(html: str) -> bool:
    lowered = html.lower()
    return any(hint in lowered for hint in BLOCK_HINTS)


def extract_publication_id(href: str | None) -> str | None:
    if not href:
        return None
    params = parse_qs(urlparse(href).query)
    values = params.get("citation_for_view")
    if not values:
        return None
    return normalize_publication_id(values[0])


def fetch_profile_page(
    *,
    session,
    user_id: str,
    hl: str,
    cstart: int,
    pagesize: int,
    timeout: int,
    retries: int,
):
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ScholarFetchError(
            "Missing dependencies. Run `pip install -r citation/requirements.txt`."
        ) from exc

    url = build_page_url(user_id=user_id, hl=hl, cstart=cstart, pagesize=pagesize)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = exc
        else:
            html = response.text
            if is_blocked_response(html):
                last_error = ScholarFetchError(
                    "Google Scholar returned an anti-bot page for the public profile."
                )
            else:
                return BeautifulSoup(html, "html.parser")

        if attempt < retries:
            time.sleep(min(attempt, 3))

    raise ScholarFetchError(
        f"failed to fetch Google Scholar profile page at offset {cstart}: {last_error}"
    )


def parse_total_citations(soup) -> int | None:
    fallback_value: int | None = None
    for row in soup.select("#gsc_rsb_st tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) >= 2 and fallback_value is None:
            fallback_value = extract_first_int(cells[1])
        if len(cells) >= 2 and cells[0].lower().startswith("citations"):
            return extract_first_int(cells[1])
    return fallback_value


def parse_publications_on_page(soup) -> dict[str, dict[str, int | str]]:
    publications: dict[str, dict[str, int | str]] = {}

    for row in soup.select("tr.gsc_a_tr"):
        title_link = row.select_one("a.gsc_a_at")
        if title_link is None:
            continue

        publication_id = extract_publication_id(title_link.get("href"))
        if not publication_id:
            continue

        title = title_link.get_text(" ", strip=True)
        citations_element = row.select_one(".gsc_a_c a, .gsc_a_c span")
        year_element = row.select_one(".gsc_a_y span, .gsc_a_y")

        entry: dict[str, int | str] = {
            "title": title,
            "num_citations": extract_first_int(
                citations_element.get_text(" ", strip=True) if citations_element else ""
            )
            or 0,
        }

        year = extract_first_int(year_element.get_text(" ", strip=True) if year_element else "")
        if year is not None:
            entry["year"] = year

        publications[publication_id] = entry

    return publications


def collect_stats(
    *,
    user_id: str,
    hl: str,
    pagesize: int,
    max_pages: int,
    timeout: int,
    retries: int,
) -> dict[str, object]:
    try:
        import requests
    except ImportError as exc:
        raise ScholarFetchError(
            "requests is not installed. Run `pip install -r citation/requirements.txt`."
        ) from exc

    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    publications: dict[str, dict[str, int | str]] = {}
    scholar_name: str | None = None
    citedby: int | None = None

    for page_index in range(max_pages):
        soup = fetch_profile_page(
            session=session,
            user_id=user_id,
            hl=hl,
            cstart=page_index * pagesize,
            pagesize=pagesize,
            timeout=timeout,
            retries=retries,
        )

        if page_index == 0:
            name_element = soup.select_one("#gsc_prf_in")
            scholar_name = name_element.get_text(" ", strip=True) if name_element else None
            citedby = parse_total_citations(soup)
            if scholar_name is None or citedby is None:
                raise ScholarFetchError("Google Scholar profile page did not contain author stats.")

        page_publications = parse_publications_on_page(soup)
        if not page_publications:
            if page_index == 0:
                raise ScholarFetchError("Google Scholar profile page did not contain publications.")
            break

        new_count = 0
        for publication_id, publication in page_publications.items():
            if publication_id not in publications:
                new_count += 1
            publications[publication_id] = publication

        if len(page_publications) < pagesize or new_count == 0:
            break

    if citedby is None:
        raise ScholarFetchError("Google Scholar profile page did not contain total citations.")

    return build_payload(
        user_id=user_id,
        hl=hl,
        scholar_name=scholar_name,
        citedby=citedby,
        publications=publications,
    )


def write_stats(output_path: str, payload: dict[str, object]) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> int:
    args = parse_args()
    try:
        payload = collect_stats(
            user_id=args.user_id,
            hl=args.hl,
            pagesize=args.pagesize,
            max_pages=args.max_pages,
            timeout=args.timeout,
            retries=args.retries,
        )
        destination = write_stats(args.output, payload)
    except ScholarFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote Google Scholar stats for {args.user_id} "
        f"(cited by {payload['citedby']}, backend=direct-html) to {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
